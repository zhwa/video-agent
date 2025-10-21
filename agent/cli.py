from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Optional

from .langgraph_nodes import build_graph_description, run_graph_description
from .adapters.factory import get_llm_adapter


def main():
    p = argparse.ArgumentParser(description="Run the LangGraph lecture agent (PoC)")
    p.add_argument("path", help="Path to input file (PDF/MD) or directory")
    p.add_argument("--provider", help="LLM provider override (vertex|openai)")
    p.add_argument("--out", help="Output folder to write results", default="workspace/out")
    p.add_argument("--llm-retries", help="Max retries for LLM client", type=int, default=None)
    p.add_argument("--llm-out", help="Directory for LLM attempt logs", default=None)
    p.add_argument("--max-workers", help="Max concurrent chapter generation workers", type=int, default=None)
    p.add_argument("--max-slide-workers", help="Max concurrent slide asset generation workers", type=int, default=None)
    p.add_argument("--slide-rate", help="Rate limit for slide asset generation (calls/sec)", type=float, default=None)
    p.add_argument("--compose", action="store_true", help="Compose per-chapter videos after generation")
    p.add_argument("--compose-workers", help="Max concurrent chapter composition workers", type=int, default=None)
    p.add_argument("--compose-rate", help="Rate limit for chapter composition (calls/sec)", type=float, default=None)
    p.add_argument("--merge", action="store_true", help="Merge per-chapter videos into a final course video")
    p.add_argument("--transition", help="Transition duration (seconds) between chapter videos", type=float, default=0.0)
    p.add_argument("--llm-rate", help="LLM rate limit in calls per second", type=float, default=None)
    p.add_argument("--resume", help="Resume a previous run by run_id", default=None)
    p.add_argument("--list-runs", help="List saved runs", action="store_true")
    p.add_argument("--inspect", help="Inspect a run metadata by run_id", default=None)
    args = p.parse_args()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Configure LLM client via environment (simple approach)
    if args.llm_retries is not None:
        os.environ.setdefault("LLM_MAX_RETRIES", str(args.llm_retries))
    if args.llm_out:
        os.environ.setdefault("LLM_OUT_DIR", args.llm_out)
    if args.max_workers is not None:
        os.environ.setdefault("MAX_WORKERS", str(args.max_workers))
    if args.max_slide_workers is not None:
        os.environ.setdefault("MAX_SLIDE_WORKERS", str(args.max_slide_workers))
    if args.slide_rate is not None:
        os.environ.setdefault("SLIDE_RATE_LIMIT", str(args.slide_rate))
    if args.llm_rate is not None:
        os.environ.setdefault("LLM_RATE_LIMIT", str(args.llm_rate))
    if args.compose_workers is not None:
        os.environ.setdefault("MAX_COMPOSER_WORKERS", str(args.compose_workers))
    if args.compose_rate is not None:
        os.environ.setdefault("COMPOSER_RATE_LIMIT", str(args.compose_rate))

    # Handle runs listing/inspection early
    if args.list_runs:
        try:
            from .runs import list_runs

            runs = list_runs()
            print("Runs:")
            for rid, meta in runs.items():
                print(f"- {rid}: {meta.get('path') if meta else 'unknown'}")
        except Exception:
            print("Failed to list runs")
        return

    if args.inspect:
        try:
            from .runs import get_run_metadata

            meta = get_run_metadata(args.inspect)
            if meta:
                print(json.dumps(meta, ensure_ascii=False, indent=2))
            else:
                print("No metadata found for run:", args.inspect)
        except Exception:
            print("Failed to inspect run", args.inspect)
        return

    desc = build_graph_description(args.path)
    adapter = None
    if args.provider:
        adapter = get_llm_adapter(args.provider)
    result = run_graph_description(desc, llm_adapter=adapter, resume_run_id=args.resume)
    out_file = out_dir / (Path(args.path).stem + "_results.json")
    out_file.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Results written to:", out_file)
    # Optionally compose per-chapter videos
    if args.compose:
        try:
            from .video_composer import VideoComposer
            from .parallel import run_tasks_in_threads
        except Exception:
            print("VideoComposer not available. Install moviepy to enable composition.")
            return
        composer = VideoComposer()
        # Prefer run_id returned by the graph runner to maintain consistency
        run_id = result.get("run_id") or str(out_dir.name)
        chapters = result.get("script_gen", [])
        try:
            max_workers = int(os.getenv("MAX_COMPOSER_WORKERS", "1"))
        except Exception:
            max_workers = 1
        try:
            rate_limit = float(os.getenv("COMPOSER_RATE_LIMIT", "0"))
            if rate_limit <= 0:
                rate_limit = None
        except Exception:
            rate_limit = None

        # Load existing composition checkpoint if any (resume support)
        try:
            from .runs import load_checkpoint, save_checkpoint

            ckpt = load_checkpoint(run_id) or {}
            existing_composition = ckpt.get("composition") or []
        except Exception:
            existing_composition = []

        # If we've already composed some chapters, avoid parallel generation to
        # reduce race conditions and incrementally save per-chapter results.
        if max_workers and max_workers > 1 and len(chapters) > 1 and not existing_composition:
            try:
                from .composer_runner import compose_chapters_parallel
                comp_results = compose_chapters_parallel(composer, chapters, run_id, max_workers=max_workers, rate_limit=rate_limit)
                # Merge results into checkpoint and attach to chapters
                composition_list = []
                for c, comp_res in zip(chapters, comp_results):
                    composition_list.append({"chapter_id": c.get("chapter_id"), **(comp_res or {})})
                try:
                    save_checkpoint(run_id, "composition", composition_list)
                except Exception:
                    pass
                for ch, comp_res in zip(chapters, comp_results):
                    ch["composition"] = comp_res
            except Exception:
                # fallback to existing thread-based approach
                tasks = []
                for c in chapters:
                    def make_task(ch=c):
                        def _task():
                            return composer.compose_and_upload_chapter_video(ch.get("slides", []), run_id, ch.get("chapter_id"))

                        return _task

                    tasks.append(make_task())
                comp_results = run_tasks_in_threads(tasks, max_workers=max_workers, rate_limit=rate_limit)
                # Merge results into checkpoint and attach to chapters
                composition_list = existing_composition.copy()
                for c, comp_res in zip(chapters, comp_results):
                    composition_list.append({"chapter_id": c.get("chapter_id"), **(comp_res or {})})
                try:
                    save_checkpoint(run_id, "composition", composition_list)
                except Exception:
                    pass
                for ch, comp_res in zip(chapters, comp_results):
                    ch["composition"] = comp_res
        else:
            # Sequential composition: use existing composition checkpoint and
            # only generate missing chapter videos to support resume.
            composition_list = existing_composition.copy()
            # Helper to find existing composition by chapter
            def _find_comp(ch_id):
                for item in composition_list:
                    if item.get("chapter_id") == ch_id:
                        return item
                return None

            for chap in chapters:
                chapter_id = chap.get("chapter_id")
                existing = _find_comp(chapter_id)
                if existing:
                    chap["composition"] = existing
                    continue
                slides = chap.get("slides", [])
                comp_res = composer.compose_and_upload_chapter_video(slides, run_id, chapter_id)
                # attach composition results to results structure
                chap["composition"] = comp_res
                # append and save checkpoint incrementally
                composition_list.append({"chapter_id": chapter_id, **(comp_res or {})})
                try:
                    save_checkpoint(run_id, "composition", composition_list)
                except Exception:
                    pass
        # Re-write the results with composition URLs
        out_file.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        print("Composition completed and results updated:", out_file)
    if args.merge:
        # Gather video URLs from composition results
        vids = []
        for chap in result.get("script_gen", []):
            comp = chap.get("composition") or {}
            vid = comp.get("video_url")
            if vid:
                vids.append(vid)
        if not vids:
            print("No chapter videos found to merge. Run --compose first or ensure composition produced videos.")
        else:
            try:
                from .video_composer import VideoComposer
            except Exception:
                print("VideoComposer not available. Install moviepy to enable merging.")
                return
            composer = VideoComposer()
            out_course = out_dir / (Path(args.path).stem + "_course.mp4")
            local_out = str(out_course)
            local_merged = composer.merge_videos(vids, local_out, transition_sec=args.transition)
            # Optionally upload via storage adapter
            from .storage import get_storage_adapter

            storage = get_storage_adapter()
            if storage:
                try:
                    url = storage.upload_file(local_merged, dest_path=f"videos/{Path(args.path).stem}_course.mp4")
                    print("Course video uploaded to:", url)
                except Exception:
                    print("Failed to upload course video; left local copy at:", local_merged)
            else:
                print("Course video written to:", local_merged)


if __name__ == "__main__":
    main()
