from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Dict, Any, List


class LLMAdapter(ABC):
    """Abstract interface for LLM adapters used to generate slide plans.

    Implementations should implement generate_from_prompt(prompt) which is
    used by higher-level clients for retries and repair. For backwards
    compatibility, adapters may implement generate_slide_plan.
    """

    @abstractmethod
    def generate_from_prompt(self, prompt: str) -> Any:
        """Generate a raw response using the given prompt.

        May return a string or a dict. The caller (LLMClient) will parse JSON
        and validate schema.
        """
        raise NotImplementedError()

    def generate_slide_plan(
        self,
        chapter_text: str,
        max_slides: int | None = None,
        run_id: str | None = None,
        chapter_id: str | None = None,
    ) -> Dict[str, Any]:
        """Optional convenience method: adapters can implement this directly.

        Default implementation raises NotImplementedError to signal callers
        to use generate_from_prompt instead. New optional parameters
        `run_id` and `chapter_id` are provided so callers can pass through
        identifiers used for logging or artifact names.
        """
        raise NotImplementedError()


class DummyLLMAdapter(LLMAdapter):
    """A deterministic stub adapter for testing and local development.

    It splits the chapter into simple sentences and groups them into slides.
    """

    def generate_slide_plan(self, chapter_text: str, max_slides: int | None = None, run_id: str | None = None, chapter_id: str | None = None) -> Dict[str, Any]:
        # Very small heuristic: split on sentence-ending punctuation
        import re

        sentences = [s.strip() for s in re.split(r"(?<=[\.!\?])\s+", chapter_text) if s.strip()]
        if not sentences:
            return {"slides": []}
        if max_slides is None:
            max_slides = min(6, max(1, len(sentences) // 3))
        # Group sentences into roughly equal buckets
        per = max(1, len(sentences) // max_slides)
        slides: List[Dict[str, Any]] = []
        i = 0
        slide_no = 1
        while i < len(sentences) and len(slides) < max_slides:
            group = sentences[i : i + per]
            title = group[0][:60]
            bullets = [s for s in group[:4]]
            slides.append(
                {
                    "id": f"s{slide_no:02d}",
                    "title": title,
                    "bullets": bullets,
                    "visual_prompt": f"illustration for: {title}",
                    "estimated_duration_sec": max(20, min(120, sum(len(x) for x in group) // 5)),
                    "speaker_notes": " ".join(group),
                }
            )
            slide_no += 1
            i += per
        return {"slides": slides}
    def generate_from_prompt(self, prompt: str) -> Any:
        # Attempt to extract chapter_text from prompt using simple heuristic
        import re

        m = re.search(r"-----\n(.*)\n-----", prompt, flags=re.DOTALL)
        if m:
            chapter_text = m.group(1).strip()
        else:
            # fallback: try last lines
            chapter_text = prompt[-4000:]
        return self._heuristic_plan(chapter_text)

    def _heuristic_plan(self, chapter_text: str, max_slides: int | None = None) -> Dict[str, Any]:
        import re

        sentences = [s.strip() for s in re.split(r"(?<=[\.\?\!])\s+", chapter_text) if s.strip()]
        if not sentences:
            return {"slides": []}
        if max_slides is None:
            max_slides = min(6, max(1, len(sentences) // 3))
        per = max(1, len(sentences) // max_slides)
        slides: List[Dict[str, Any]] = []
        i = 0
        slide_no = 1
        while i < len(sentences) and len(slides) < max_slides:
            group = sentences[i : i + per]
            title = group[0][:60]
            bullets = [s for s in group[:4]]
            slides.append(
                {
                    "id": f"s{slide_no:02d}",
                    "title": title,
                    "bullets": bullets,
                    "visual_prompt": f"illustration for: {title}",
                    "estimated_duration_sec": max(20, min(120, sum(len(x) for x in group) // 5)),
                    "speaker_notes": " ".join(group),
                }
            )
            slide_no += 1
            i += per
        return {"slides": slides}

    # ...existing code...  (old duplicate generate_slide_plan removed)
