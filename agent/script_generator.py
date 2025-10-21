from __future__ import annotations

from typing import Dict, Any, List

from .adapters.llm import LLMAdapter
from .adapters import get_tts_adapter
from .storage import get_storage_adapter
import os
import uuid


def generate_slides_for_chapter(
    chapter: Dict[str, Any], llm_adapter: LLMAdapter, max_slides: int | None = None, run_id: str | None = None
) -> Dict[str, Any]:
    """Generate a slide plan for a single chapter using the provided LLM adapter.

    The returned structure mirrors the adapter output but attaches chapter id.
    """
    text = chapter.get("text", "")
    # Pass through run_id and chapter id to support per-chapter logging by LLMClient
    plan = llm_adapter.generate_slide_plan(text, max_slides=max_slides, run_id=run_id, chapter_id=chapter.get("id"))
    slides: List[Dict[str, Any]] = plan.get("slides", [])
    # Normalize each slide and add chapter context
    normalized = []
    for s in slides:
        normalized.append({
            "chapter_id": chapter.get("id"),
            "slide_id": s.get("id"),
            "title": s.get("title"),
            "bullets": s.get("bullets", []),
            "visual_prompt": s.get("visual_prompt"),
            "estimated_duration_sec": s.get("estimated_duration_sec", 60),
            "speaker_notes": s.get("speaker_notes", ""),
        })
    # Optionally synthesize TTS for each slide if TTS provider configured
    tts_provider = os.getenv("TTS_PROVIDER")
    if tts_provider:
        tts = get_tts_adapter(tts_provider)
        # storage adapter for uploading generated audio
        storage = get_storage_adapter()
        for slide in normalized:
            text = slide.get("speaker_notes") or ""
            # create a per-slide output path
            out_dir = os.getenv("LLM_OUT_DIR") or "workspace/out"
            os.makedirs(out_dir, exist_ok=True)
            filename = f"{run_id or 'run'}_{chapter.get('id')}_{slide.get('slide_id')}.mp3"
            local_path = os.path.join(out_dir, filename)
            audio_path = tts.synthesize(text, out_path=local_path)
            if storage:
                try:
                    url = storage.upload_file(audio_path, dest_path=f"tts/{filename}")
                    slide["audio_url"] = url
                except Exception:
                    slide["audio_url"] = audio_path
            else:
                slide["audio_url"] = audio_path
    return {"chapter_id": chapter.get("id"), "slides": normalized}
