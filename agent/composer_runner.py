from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from typing import List, Dict, Callable, Optional
from .parallel import run_tasks_in_threads


def compose_chapters_parallel(
    composer, chapters: List[Dict], run_id: str, max_workers: int = 2, rate_limit: Optional[float] = None
) -> List[Dict]:
    """Run composer.compose_and_upload_chapter_video in parallel for multiple chapters.

    composer: instance of VideoComposer
    chapters: list of chapter dicts (each with 'chapter_id' and 'slides')
    run_id: unique run identifier
    max_workers: concurrency limit
    rate_limit: optional calls per second limit (shared across tasks)

    Returns list of composition results (in submission order).
    """
    tasks = []
    for c in chapters:
        def make_task(ch=c):
            def _task():
                return composer.compose_and_upload_chapter_video(ch.get("slides", []), run_id, ch.get("chapter_id"))

            return _task

        tasks.append(make_task())
    return run_tasks_in_threads(tasks, max_workers=max_workers, rate_limit=rate_limit)
