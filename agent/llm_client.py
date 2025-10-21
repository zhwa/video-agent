from __future__ import annotations

import json
import os
import re
import time
from typing import Any, Callable, Dict, List, Optional

from .adapters.schema import validate_slide_plan
from .prompts import build_prompt
from .adapters.llm import LLMAdapter


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
                from .storage import get_storage_adapter

                self.storage_adapter = get_storage_adapter()
            except Exception:
                self.storage_adapter = None

        # If there is a storage adapter but no explicit out_dir, create a
        # temporary staging directory to record attempts before uploading.
        if self.out_dir:
            os.makedirs(self.out_dir, exist_ok=True)
        elif self.storage_adapter:
            import tempfile

            self.out_dir = tempfile.mkdtemp(prefix="llm_attempts_")

    def _write_attempt(self, run_id: str, chapter_id: str, attempt_no: int, prompt: str, response: Any, validation: Dict[str, Any]):
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
                # Optionally remove the local attempt after successful upload
                if remove_local:
                    try:
                        os.remove(full)
                    except Exception:
                        pass
            except Exception:
                # best-effort: don't fail the whole run if storage fails
                pass

    def _parse_json(self, text: Any) -> Optional[Dict[str, Any]]:
        if isinstance(text, dict):
            return text
        if not isinstance(text, str):
            return None
        # try straight parse
        try:
            return json.loads(text)
        except Exception:
            # extract first JSON object
            m = re.search(r"\{.*\}", text, flags=re.DOTALL)
            if not m:
                return None
            try:
                return json.loads(m.group(0))
            except Exception:
                return None

    def generate_and_validate(self, adapter: LLMAdapter, chapter_text: str, max_slides: Optional[int] = None, run_id: Optional[str] = None, chapter_id: Optional[str] = None) -> Dict[str, Any]:
        """Generate slide plan using adapter and validate; attempts repairs when invalid.

        Returns the (possibly repaired) parsed plan and metadata about attempts.
        """
        attempt = 1
        prompt = build_prompt(chapter_text, max_slides=max_slides)
        last_response = None
        attempts_info: List[Dict[str, Any]] = []

        while attempt <= self.max_retries:
            # call adapter
            try:
                if hasattr(adapter, "generate_from_prompt"):
                    raw = adapter.generate_from_prompt(prompt)
                else:
                    # fallback to generate_slide_plan which takes chapter_text
                    raw = adapter.generate_slide_plan(chapter_text, max_slides=max_slides)
            except Exception as e:
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

            if ok and parsed:
                # Archive attempts (best-effort) if storage adapter configured
                try:
                    self.archive_attempts_to_storage(run_id or "run", chapter_id or "chapter")
                except Exception:
                    pass
                return {"plan": parsed, "attempts": attempts_info}

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

        # After retries, fallback to a deterministic local adapter to avoid recursive calls
        try:
            # Use the local DummyLLMAdapter as a safe deterministic fallback
            from .adapters.llm import DummyLLMAdapter

            fallback = DummyLLMAdapter().generate_slide_plan(chapter_text, max_slides=max_slides)
        except Exception:
            fallback = {"slides": []}

        parsed_fallback = self._parse_json(fallback) or fallback
        try:
            self.archive_attempts_to_storage(run_id or "run", chapter_id or "chapter")
        except Exception:
            pass
        return {"plan": parsed_fallback, "attempts": attempts_info, "fallback_used": True}
