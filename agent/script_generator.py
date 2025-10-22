from __future__ import annotations

import logging
import os
import time
import uuid
from typing import Dict, Any, List

from .google import GoogleServices, get_storage_adapter
from .parallel import run_tasks_in_threads
from .monitoring import record_timing, increment, get_logger

logger = get_logger(__name__)


def generate_slides_for_chapter(
    chapter: Dict[str, Any], google: GoogleServices, max_slides: int | None = None, run_id: str | None = None
) -> Dict[str, Any]:
    """Generate a slide plan for a single chapter using Google services.

    The returned structure mirrors the output but attaches chapter id.
    """
    text = chapter.get("text", "")
    # Pass through run_id and chapter id to support per-chapter logging by LLMClient
    start = time.time()
    plan = google.generate_slide_plan(text, max_slides=max_slides, run_id=run_id, chapter_id=chapter.get("id"))
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
    # Optionally synthesize TTS and generate images for each slide
    enable_tts = os.getenv("ENABLE_TTS", "true").lower() in ("true", "1", "yes")
    enable_images = os.getenv("ENABLE_IMAGES", "true").lower() in ("true", "1", "yes")
    storage = get_storage_adapter()

    def _process_slide(slide: dict) -> dict:
        # Generate audio if TTS enabled
        if enable_tts:
            st = time.time()
            try:
                text = slide.get("speaker_notes") or ""
                out_dir = os.getenv("LLM_OUT_DIR") or "workspace/out"
                os.makedirs(out_dir, exist_ok=True)
                filename = f"{run_id or 'run'}_{chapter.get('id')}_{slide.get('slide_id')}.mp3"
                local_path = os.path.join(out_dir, filename)
                audio_path = google.synthesize_speech(text, out_path=local_path)
                if storage:
                    try:
                        url = storage.upload_file(audio_path, dest_path=f"tts/{filename}")
                        slide["audio_url"] = url
                        logger.debug("Uploaded audio to: %s", url)
                    except OSError as e:
                        logger.warning("Failed to upload audio, using local path: %s", e)
                        slide["audio_url"] = audio_path
                else:
                    slide["audio_url"] = audio_path
            except Exception as e:
                logger.error("Failed to synthesize audio for slide %s: %s", slide.get('slide_id'), e)
                raise
            finally:
                record_timing("tts_generation_sec", time.time() - st)

        # Generate image if images enabled
        if enable_images:
            st_img = time.time()
            try:
                prompt = slide.get("visual_prompt") or slide.get("title") or "visual"
                out_dir = os.getenv("LLM_OUT_DIR") or "workspace/out"
                os.makedirs(out_dir, exist_ok=True)
                filename = f"{run_id or 'run'}_{chapter.get('id')}_{slide.get('slide_id')}.png"
                local_path = os.path.join(out_dir, filename)
                image_path = google.generate_image(prompt, out_path=local_path)
                if storage:
                    try:
                        url = storage.upload_file(image_path, dest_path=f"images/{filename}")
                        slide["image_url"] = url
                        logger.debug("Uploaded image to: %s", url)
                    except OSError as e:
                        logger.warning("Failed to upload image, using local path: %s", e)
                        slide["image_url"] = image_path
                else:
                    slide["image_url"] = image_path
            except Exception as e:
                logger.error("Failed to generate image for slide %s: %s", slide.get('slide_id'), e)
                raise
            finally:
                record_timing("image_generation_sec", time.time() - st_img)
        return slide

    # If either TTS or images are enabled, process slides (possibly in parallel)
    if enable_tts or enable_images:
        try:
            max_workers = int(os.getenv("MAX_SLIDE_WORKERS", "1"))
        except (ValueError, TypeError):
            logger.warning("Invalid MAX_SLIDE_WORKERS, using default of 1")
            max_workers = 1
        try:
            rate_limit = float(os.getenv("SLIDE_RATE_LIMIT", "0"))
            if rate_limit <= 0:
                rate_limit = None
        except (ValueError, TypeError):
            logger.warning("Invalid SLIDE_RATE_LIMIT, using default of no limit")
            rate_limit = None

        if max_workers and max_workers > 1 and len(normalized) > 1:
            logger.debug("Processing %d slides in parallel with %d workers", len(normalized), max_workers)
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
            logger.debug("Processing %d slides sequentially", len(normalized))
            for slide in normalized:
                _process_slide(slide)
    return {"chapter_id": chapter.get("id"), "slides": normalized}
