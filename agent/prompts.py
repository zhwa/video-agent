from __future__ import annotations

from pathlib import Path
from typing import Optional

TEMPLATE_PATH = Path(__file__).parents[1] / "templates" / "slide_prompt.txt"


def load_template() -> str:
    if TEMPLATE_PATH.exists():
        return TEMPLATE_PATH.read_text(encoding="utf-8")
    # fallback default
    return (
        "Return a JSON object with key 'slides'. Each slide must contain id,title,bullets,visual_prompt,estimated_duration_sec,speaker_notes."
    )


def build_prompt(chapter_text: str, max_slides: Optional[int] = None, schema_description: Optional[str] = None) -> str:
    tmpl = load_template()
    if max_slides is None:
        max_slides = 6
    if schema_description is None:
        # Build a short description from required keys
        from .adapters.schema import REQUIRED_SLIDE_KEYS

        schema_description = ", ".join(REQUIRED_SLIDE_KEYS)
    return tmpl.format(chapter_text=chapter_text, max_slides=max_slides, schema_description=schema_description)
