from __future__ import annotations

import argparse
import json
import logging
import os
from pathlib import Path
from typing import Optional

from .graphflow_graph import create_video_agent_graph, prepare_graph_input
from .runs_checkpoint import checkpoint_invoke
from .adapters.factory import get_llm_adapter
from .monitoring import configure_logging, get_logger

# Will be configured on startup
logger: logging.Logger = None


def _filter_serializable_result(result: dict) -> dict:
    """Filter out non-JSON-serializable objects from result dict.

    Removes LLM adapters and other complex objects that can't be
    serialized to JSON.

    Args:
        result: Result dictionary from graph execution

    Returns:
        Filtered dictionary with only JSON-serializable values
    """
    filtered = {}
    for key, value in result.items():
        # Skip adapter objects
        if key in ("llm_adapter", "llm_adapter_used"):
            # Keep adapter name but not the object itself
            if key == "llm_adapter_used" and isinstance(value, str):
                filtered[key] = value
            continue

        try:
            # Test if serializable
            json.dumps(value)
            filtered[key] = value
        except (TypeError, ValueError):
            # Skip non-serializable values
            logger.debug(f"Skipping non-serializable field in result: {key}")
            continue

    return filtered


def main():
    p = argparse.ArgumentParser(description="Run the GraphFlow video composition agent")
    p.add_argument("path", help="Path to input file (PDF/MD) or directory")
    p.add_argument("--provider", help="LLM provider override (vertex|openai)")
    p.add_argument("--out", help="Output folder to write results", default="workspace/out")
    p.add_argument("--llm-retries", help="Max retries for LLM client", type=int, default=None)
    p.add_argument("--llm-out", help="Directory for LLM attempt logs", default=None)
    p.add_argument("--max-workers", help="Max concurrent chapter generation workers", type=int, default=None)
    p.add_argument("--max-slide-workers", help="Max concurrent slide asset generation workers", type=int, default=None)
    p.add_argument("--slide-rate", help="Rate limit for slide asset generation (calls/sec)", type=float, default=None)
    p.add_argument("--full-pipeline", action="store_true", help="Run complete pipeline: script generation + video composition + merge (recommended)")
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

    # Configure logging
    global logger
    log_dir = args.out if args.out else None
    logger = configure_logging(log_dir=log_dir, level=logging.INFO)
    logger.info("Starting video agent with args: %s", args)

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    logger.debug("Output directory: %s", out_dir)

    # If --full-pipeline is set, enable compose and merge automatically
    if args.full_pipeline:
        args.compose = True
        args.merge = True
        # Auto-configure LLM output dir if not specified
        if not args.llm_out:
            args.llm_out = str(out_dir / "llm_logs")

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
            logger.info("Listed %d runs", len(runs))
        except OSError as e:
            logger.error("Failed to list runs: %s", e)
        except Exception as e:
            logger.error("Unexpected error listing runs: %s", e)
        return

    if args.inspect:
        try:
            from .runs import get_run_metadata
            meta = get_run_metadata(args.inspect)
            if meta:
                print(json.dumps(meta, ensure_ascii=False, indent=2))
                logger.info("Inspected run: %s", args.inspect)
            else:
                print("No metadata found for run:", args.inspect)
                logger.warning("No metadata found for run: %s", args.inspect)
        except OSError as e:
            logger.error("Failed to read run metadata: %s", e)
        except Exception as e:
            logger.error("Unexpected error inspecting run %s: %s", args.inspect, e)
        return

    # Create and execute the GraphFlow graph
    graph = create_video_agent_graph()
    adapter = None
    if args.provider:
        adapter = get_llm_adapter(args.provider)
    
    # Prepare initial state
    initial_state = prepare_graph_input(
        input_path=args.path,
        run_id=args.resume,
        llm_adapter=adapter,
        full_pipeline=args.full_pipeline,
        compose=args.compose,
        merge=args.merge,
    )
    
    try:
        result = checkpoint_invoke(graph, initial_state, run_id=args.resume)
        logger.info("Graph execution completed successfully")
    except ValueError as e:
        logger.error("Invalid input: %s", e)
        raise
    except Exception as e:
        logger.error("Graph execution failed: %s", e)
        raise
    
    out_file = out_dir / (Path(args.path).stem + "_results.json")
    try:
        # Filter out non-serializable objects from result
        serializable_result = _filter_serializable_result(result)
        out_file.write_text(json.dumps(serializable_result, ensure_ascii=False, indent=2), encoding="utf-8")
        print("Results written to:", out_file)
        logger.info("Results written to: %s", out_file)
    except OSError as e:
        logger.error("Failed to write results file: %s", e)
        raise
    
    # Optionally compose per-chapter videos
    if args.compose:
        try:
            from .video_composer import VideoComposer
            from .parallel import run_tasks_in_threads
        except ImportError as e:
            logger.error("VideoComposer not available (moviepy not installed): %s", e)
            print("VideoComposer not available. Install moviepy to enable composition.")
            return
        
        try:
            composer = VideoComposer()
            # Prefer run_id returned by the graph runner to maintain consistency
            run_id = result.get("run_id") or str(out_dir.name)
            chapters = result.get("script_gen", [])
            logger.info("Starting composition for %d chapters", len(chapters))
            
            # Parse configuration with better error handling
            try:
                max_workers = int(os.getenv("MAX_COMPOSER_WORKERS", "1"))
            except (ValueError, TypeError):
                logger.warning("Invalid MAX_COMPOSER_WORKERS, using default of 1")
                max_workers = 1
            
            try:
                rate_limit = float(os.getenv("COMPOSER_RATE_LIMIT", "0"))
                if rate_limit <= 0:
                    rate_limit = None
            except (ValueError, TypeError):
                logger.warning("Invalid COMPOSER_RATE_LIMIT, using default of no limit")
                rate_limit = None

            # Load existing composition checkpoint if any (resume support)
            existing_composition = []
            try:
                from .runs import load_checkpoint, save_checkpoint
                ckpt = load_checkpoint(run_id) or {}
                existing_composition = ckpt.get("composition") or []
                logger.info("Loaded %d existing compositions from checkpoint", len(existing_composition))
            except OSError as e:
                logger.debug("No checkpoint found (expected on first run): %s", e)
            except Exception as e:
                logger.warning("Failed to load checkpoint: %s", e)

            # If we've already composed some chapters, avoid parallel generation to
            # reduce race conditions and incrementally save per-chapter results.
            if max_workers and max_workers > 1 and len(chapters) > 1 and not existing_composition:
                try:
                    # Parallel composition using run_tasks_in_threads
                    from .parallel import run_tasks_in_threads
                    
                    # Create composition tasks for each chapter
                    def make_task(ch):
                        def _task():
                            return composer.compose_and_upload_chapter_video(
                                ch.get("slides", []), run_id, ch.get("chapter_id")
                            )
                        return _task
                    
                    tasks = [make_task(c) for c in chapters]
                    logger.info("Starting parallel composition with %d workers", max_workers)
                    comp_results = run_tasks_in_threads(tasks, max_workers=max_workers, rate_limit=rate_limit)
                    
                    # Merge results into checkpoint and attach to chapters
                    composition_list = []
                    for c, comp_res in zip(chapters, comp_results):
                        composition_list.append({"chapter_id": c.get("chapter_id"), **(comp_res or {})})
                    try:
                        save_checkpoint(run_id, "composition", composition_list)
                        logger.debug("Saved composition checkpoint")
                    except OSError as e:
                        logger.warning("Failed to save checkpoint: %s", e)
                    for ch, comp_res in zip(chapters, comp_results):
                        ch["composition"] = comp_res
                except (ImportError, AttributeError) as e:
                    logger.warning("Parallel composition not available, falling back to sequential: %s", e)
                    # fallback to sequential approach
                    composition_list = existing_composition.copy()
                    for chap in chapters:
                        chapter_id = chap.get("chapter_id")
                        existing = next((item for item in composition_list if item.get("chapter_id") == chapter_id), None)
                        if existing:
                            chap["composition"] = existing
                            logger.debug("Using cached composition for chapter %s", chapter_id)
                            continue
                        slides = chap.get("slides", [])
                        logger.debug("Composing chapter %s with %d slides", chapter_id, len(slides))
                        comp_res = composer.compose_and_upload_chapter_video(slides, run_id, chapter_id)
                        chap["composition"] = comp_res
                        composition_list.append({"chapter_id": chapter_id, **(comp_res or {})})
                        try:
                            save_checkpoint(run_id, "composition", composition_list)
                        except OSError as e:
                            logger.debug("Failed to save checkpoint after chapter %s: %s", chapter_id, e)
                except Exception as e:
                    logger.error("Error during parallel composition: %s", e)
                    raise
            else:
                # Sequential composition: use existing composition checkpoint and
                # only generate missing chapter videos to support resume.
                logger.info("Starting sequential composition")
                composition_list = existing_composition.copy()
                for chap in chapters:
                    chapter_id = chap.get("chapter_id")
                    existing = next((item for item in composition_list if item.get("chapter_id") == chapter_id), None)
                    if existing:
                        chap["composition"] = existing
                        logger.debug("Using cached composition for chapter %s", chapter_id)
                        continue
                    slides = chap.get("slides", [])
                    logger.debug("Composing chapter %s with %d slides", chapter_id, len(slides))
                    comp_res = composer.compose_and_upload_chapter_video(slides, run_id, chapter_id)
                    chap["composition"] = comp_res
                    composition_list.append({"chapter_id": chapter_id, **(comp_res or {})})
                    try:
                        save_checkpoint(run_id, "composition", composition_list)
                    except OSError as e:
                        logger.debug("Failed to save checkpoint after chapter %s: %s", chapter_id, e)
            
            # Re-write the results with composition URLs
            try:
                serializable_result = _filter_serializable_result(result)
                out_file.write_text(json.dumps(serializable_result, ensure_ascii=False, indent=2), encoding="utf-8")
                print("Composition completed and results updated:", out_file)
                logger.info("Composition completed successfully")
            except OSError as e:
                logger.error("Failed to write results after composition: %s", e)
        except Exception as e:
            logger.error("Unexpected error during composition: %s", e)
            raise
    if args.merge:
        # Gather video URLs from composition results
        vids = []
        for chap in result.get("script_gen", []):
            comp = chap.get("composition") or {}
            vid = comp.get("video_url")
            if vid:
                vids.append(vid)
        
        if not vids:
            logger.warning("No chapter videos found to merge")
            print("No chapter videos found to merge. Run --compose first or ensure composition produced videos.")
        else:
            try:
                from .video_composer import VideoComposer
            except ImportError as e:
                logger.error("VideoComposer not available (moviepy not installed): %s", e)
                print("VideoComposer not available. Install moviepy to enable merging.")
                return
            
            try:
                logger.info("Starting video merge with %d chapter videos", len(vids))
                composer = VideoComposer()
                out_course = out_dir / (Path(args.path).stem + "_course.mp4")
                local_out = str(out_course)
                local_merged = composer.merge_videos(vids, local_out, transition_sec=args.transition)
                logger.info("Video merge completed: %s", local_merged)
                
                # Optionally upload via storage adapter
                from .storage import get_storage_adapter
                storage = get_storage_adapter()
                if storage:
                    try:
                        url = storage.upload_file(local_merged, dest_path=f"videos/{Path(args.path).stem}_course.mp4")
                        print("Course video uploaded to:", url)
                        logger.info("Course video uploaded to: %s", url)
                    except OSError as e:
                        logger.error("Failed to upload course video: %s", e)
                        print("Failed to upload course video; left local copy at:", local_merged)
                else:
                    print("Course video written to:", local_merged)
                    logger.info("Course video written to: %s", local_merged)
            except Exception as e:
                logger.error("Error during merge: %s", e)
                raise


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        logger.info("Execution interrupted by user") if logger else None
        exit(1)
    except Exception as e:
        print(f"\nFatal error: {e}")
        logger.critical("Fatal error: %s", e) if logger else None
        exit(1)
