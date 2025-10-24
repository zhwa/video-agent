from __future__ import annotations
import json
import os
import time
import json_repair
from typing import Any, Optional, Protocol
from .google.schema import validate_slide_plan
from .prompts import build_prompt
from .monitoring import record_timing, increment, get_logger

logger = get_logger(__name__)


class LLMProvider(Protocol):
    """Protocol for LLM providers that can generate text from prompts."""
    
    def generate_from_prompt(self, prompt: str) -> str:
        """Generate text from a prompt."""
        ...


class LLMClient:
    def __init__(self, max_retries: int = 3, timeout: Optional[int] = None, out_dir: Optional[str] = None, storage_adapter: Optional[object] = None):
        self.max_retries = max_retries
        self.timeout = timeout
        self.out_dir = out_dir
        # storage adapter may be provided or discovered from env
        self.storage_adapter = storage_adapter
        if self.storage_adapter is None:
            try:
                # lazy import to avoid circulars when storage module missing
                from .google import get_storage_adapter
                self.storage_adapter = get_storage_adapter()
            except ImportError as e:
                logger.debug("Storage adapter not available: %s", e)
                self.storage_adapter = None
            except Exception as e:
                logger.warning("Failed to initialize storage adapter: %s", e)
                self.storage_adapter = None

        # If there is a storage adapter but no explicit out_dir, create a
        # temporary staging directory to record attempts before uploading.
        if self.out_dir:
            os.makedirs(self.out_dir, exist_ok=True)
        elif self.storage_adapter:
            import tempfile

            self.out_dir = tempfile.mkdtemp(prefix="llm_attempts_")

    def _write_attempt(self, run_id: str, chapter_id: str, attempt_no: int, prompt: str, response: Any, validation: dict[str, Any]):
        if not self.out_dir:
            return
        base = os.path.join(self.out_dir, run_id or "run", chapter_id or "chapter")
        os.makedirs(base, exist_ok=True)
        with open(os.path.join(base, f"attempt_{attempt_no:02d}_prompt.txt"), "w", encoding="utf-8") as f:
            f.write(prompt)
        with open(os.path.join(base, f"attempt_{attempt_no:02d}_response.txt"), "w", encoding="utf-8") as f:
            f.write(json.dumps(response, ensure_ascii=False, indent=2) if not isinstance(response, str) else response)
        with open(os.path.join(base, f"attempt_{attempt_no:02d}_validation.json"), "w", encoding="utf-8") as f:
            f.write(json.dumps(validation, ensure_ascii=False, indent=2))

    def archive_attempts_to_storage(self, run_id: str, chapter_id: str) -> None:
        """Upload all locally recorded attempts for a given run/chapter to the
        configured storage adapter. This is optional and a no-op if no storage
        adapter is set.
        """
        if not self.storage_adapter or not self.out_dir:
            return
        base = os.path.join(self.out_dir, run_id or "run", chapter_id or "chapter")
        if not os.path.exists(base):
            return
        remove_local = os.getenv("LLM_ARCHIVE_CLEANUP", "false").lower() == "true"
        for fname in os.listdir(base):
            full = os.path.join(base, fname)
            dest_path = f"{run_id}/{chapter_id}/{fname}"
            try:
                url = self.storage_adapter.upload_file(full, dest_path=dest_path)
                # Write a small sidecar mapping for traceability
                with open(full + ".uploaded", "w", encoding="utf-8") as f:
                    f.write(url)
                # Record artifact in run metadata (best-effort)
                try:
                    from .runs import add_run_artifact
                    add_run_artifact(run_id, "llm_attempt", url, metadata={"file": fname})
                except ImportError:
                    logger.debug("add_run_artifact not available")
                except Exception as e:
                    logger.debug("Failed to add run artifact: %s", e)
                # Optionally remove the local attempt after successful upload
                if remove_local:
                    try:
                        os.remove(full)
                        logger.debug("Removed archived local attempt: %s", full)
                    except OSError as e:
                        logger.warning("Failed to remove archived attempt: %s", e)
            except OSError as e:
                logger.warning("Failed to upload attempt to storage: %s", e)
            except Exception as e:
                logger.warning("Unexpected error archiving attempts: %s", e)

    def _parse_json(self, text: Any) -> Optional[dict[str, Any]]:
        """Parse JSON from text using json_repair library.
        
        Handles malformed JSON commonly produced by LLMs (missing quotes,
        trailing commas, incomplete structures, etc.)
        """
        # If already a dict, return as-is
        if isinstance(text, dict):
            logger.debug("Input is already a dict")
            return text

        # If not a string, can't parse JSON
        if not isinstance(text, str):
            logger.debug("Input is not a string or dict, cannot parse JSON")
            return None

        # Use json_repair to handle malformed JSON
        try:
            parsed = json_repair.loads(text)
            if isinstance(parsed, dict):
                logger.debug("Successfully parsed JSON with json_repair")
                return parsed
            else:
                logger.debug("Parsed result is not a dict: %s", type(parsed))
                return None
        except Exception as e:
            logger.debug("json_repair parsing failed: %s", e)
            return None

    def generate_and_validate(self, provider: LLMProvider, chapter_text: str, max_slides: Optional[int] = None, run_id: Optional[str] = None, chapter_id: Optional[str] = None) -> dict[str, Any]:
        """Generate slide plan using provider and validate; attempts repairs when invalid.

        Returns the (possibly repaired) parsed plan and metadata about attempts.
        
        Args:
            provider: Any object with a generate_from_prompt(prompt: str) -> str method
            chapter_text: The chapter content to generate slides from
            max_slides: Optional maximum number of slides
            run_id: Optional run identifier for tracking
            chapter_id: Optional chapter identifier for tracking
        """
        attempt = 1
        prompt = build_prompt(chapter_text, max_slides=max_slides)
        attempts_info: list[dict[str, Any]] = []

        while attempt <= self.max_retries:
            # call provider
            start = time.time()
            try:
                raw = provider.generate_text(prompt)
            except ValueError as e:
                logger.error("Validation error from LLM provider: %s", e)
                raw = {"error": str(e)}
            except Exception as e:
                logger.error("Error calling LLM provider on attempt %d: %s", attempt, e)
                raw = {"error": str(e)}

            parsed = self._parse_json(raw)
            ok = False
            errors = []
            if parsed and isinstance(parsed, dict):
                ok, errors = validate_slide_plan(parsed)
            else:
                errors.append("No parseable JSON found in response")

            validation = {"ok": ok, "errors": errors}
            self._write_attempt(run_id or "run", chapter_id or "chapter", attempt, prompt, raw, validation)
            attempts_info.append({"attempt": attempt, "response_raw": raw, "validation": validation})

            # telemetry: record attempt duration and count
            elapsed = time.time() - start
            try:
                increment("llm_attempts")
                record_timing("llm_attempt_duration_sec", elapsed)
            except Exception as e:
                logger.debug("Failed to record telemetry: %s", e)

            if ok and parsed:
                logger.info("LLM validation passed on attempt %d", attempt)
                # Archive attempts (best-effort) if storage adapter configured
                try:
                    self.archive_attempts_to_storage(run_id or "run", chapter_id or "chapter")
                except Exception as e:
                    logger.warning("Failed to archive attempts: %s", e)
                # telemetry: mark success
                try:
                    increment("llm_success")
                except Exception as e:
                    logger.debug("Failed to record success telemetry: %s", e)
                return {"plan": parsed, "attempts": attempts_info}

            logger.debug("LLM validation failed on attempt %d with errors: %s", attempt, errors)
            
            # Prepare repair prompt
            repair_prompt = (
                "The previous response did not pass validation. The validation errors are: "
                + ", ".join(errors)
                + ". Please provide corrected JSON only, and ensure it conforms exactly to the schema described earlier."
                + "\nPrevious response:\n" + (json.dumps(raw, ensure_ascii=False) if not isinstance(raw, str) else str(raw))
                + "\nOriginal instructions:\n"
                + prompt
            )
            prompt = repair_prompt
            attempt += 1
            # optional small backoff
            time.sleep(0.5)

        # After retries, return minimal fallback plan
        logger.warning("All %d retry attempts failed, returning minimal fallback plan", self.max_retries)
        fallback = {"slides": []}

        parsed_fallback = self._parse_json(fallback) or fallback
        try:
            self.archive_attempts_to_storage(run_id or "run", chapter_id or "chapter")
        except Exception as e:
            logger.warning("Failed to archive attempts on fallback: %s", e)
        
        # telemetry: mark fallback used
        try:
            increment("llm_fallbacks")
        except Exception as e:
            logger.debug("Failed to record fallback telemetry: %s", e)
        return {"plan": parsed_fallback, "attempts": attempts_info, "fallback_used": True}