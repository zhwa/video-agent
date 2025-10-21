from __future__ import annotations

from typing import Dict, Any, List

from .adapters.llm import LLMAdapter
from .adapters import get_tts_adapter, get_image_adapter
from .storage import get_storage_adapter
from .parallel import run_tasks_in_threads
import os
import uuid
from .telemetry import record_timing, increment
import time


def generate_slides_for_chapter(
    chapter: Dict[str, Any], llm_adapter: LLMAdapter, max_slides: int | None = None, run_id: str | None = None
) -> Dict[str, Any]:
    """Generate a slide plan for a single chapter using the provided LLM adapter.

    The returned structure mirrors the adapter output but attaches chapter id.
    """
    text = chapter.get("text", "")
    # Pass through run_id and chapter id to support per-chapter logging by LLMClient
    start = time.time()
    plan = llm_adapter.generate_slide_plan(text, max_slides=max_slides, run_id=run_id, chapter_id=chapter.get("id"))
    record_timing("chapter_generation_sec", time.time() - start)
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
    # Optionally synthesize TTS and generate images for each slide if providers configured
    tts_provider = os.getenv("TTS_PROVIDER")
    image_provider = os.getenv("IMAGE_PROVIDER")
    storage = get_storage_adapter()

    def _process_slide(slide: dict) -> dict:
        # Generate audio if TTS enabled
        if tts_provider:
            st = time.time()
            tts = get_tts_adapter(tts_provider)
            text = slide.get("speaker_notes") or ""
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
            record_timing("tts_generation_sec", time.time() - st)

        # Generate image if image provider configured
        if image_provider:
            st_img = time.time()
            image_adapter = get_image_adapter(image_provider)
            prompt = slide.get("visual_prompt") or slide.get("title") or "visual"
            out_dir = os.getenv("LLM_OUT_DIR") or "workspace/out"
            os.makedirs(out_dir, exist_ok=True)
            filename = f"{run_id or 'run'}_{chapter.get('id')}_{slide.get('slide_id')}.png"
            local_path = os.path.join(out_dir, filename)
            image_path = image_adapter.generate_image(prompt, out_path=local_path)
            if storage:
                try:
                    url = storage.upload_file(image_path, dest_path=f"images/{filename}")
                    slide["image_url"] = url
                except Exception:
                    slide["image_url"] = image_path
            else:
                slide["image_url"] = image_path
            record_timing("image_generation_sec", time.time() - st_img)
        return slide

    # If either provider is enabled, process slides (possibly in parallel)
    if tts_provider or image_provider:
        try:
            max_workers = int(os.getenv("MAX_SLIDE_WORKERS", "1"))
        except Exception:
            max_workers = 1
        try:
            rate_limit = float(os.getenv("SLIDE_RATE_LIMIT", "0"))
            if rate_limit <= 0:
                rate_limit = None
        except Exception:
            rate_limit = None

        if max_workers and max_workers > 1 and len(normalized) > 1:
            tasks = []
            for s in normalized:
                def make_task(sl):
                    def _t():
                        return _process_slide(sl)

                    return _t

                tasks.append(make_task(s))
            results = run_tasks_in_threads(tasks, max_workers=max_workers, rate_limit=rate_limit)
            # results are processed in-place since slides are mutated
        else:
            for slide in normalized:
                _process_slide(slide)
    return {"chapter_id": chapter.get("id"), "slides": normalized}
