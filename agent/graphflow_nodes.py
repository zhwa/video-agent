"""GraphFlow node implementations for video agent pipeline.

This module defines the core nodes for the video generation pipeline:
- IngestNode: Reads and parses input documents
- SegmentNode: Extracts chapters from documents
- ScriptGenNode: Generates LLM-based scripts for chapters

Each node wraps existing business logic and returns updates to the graph state.
"""

from __future__ import annotations

import logging
import os
import threading
import uuid
import warnings
from typing import Any, Dict, List, Optional

from .google import GoogleServices
from .io import read_file
from .parallel import run_tasks_in_threads
from .runs_checkpoint import (
    clear_chapter_checkpoint,
    get_completed_chapters,
    save_chapter_checkpoint,
)
from .script_generator import generate_slides_for_chapter
from .segmenter import segment_pages_into_chapters, segment_text_into_chapters

logger = logging.getLogger(__name__)


def validate_vertex_credentials() -> bool:
    """Check if Vertex credentials are likely present.

    Checks GOOGLE_APPLICATION_CREDENTIALS or GOOGLE_API_KEY environment variables.
    """
    if os.getenv("GOOGLE_APPLICATION_CREDENTIALS"):
        return True
    if os.getenv("GOOGLE_API_KEY"):
        return True
    return False


def ingest_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """GraphFlow node for document ingestion.

    Reads and parses the input file. Supports PDF and Markdown formats.

    Args:
        state: Current graph state containing 'input_path'

    Returns:
        Update dict with 'file_content' containing parsed document

    Raises:
        ValueError: If file type is not supported
        FileNotFoundError: If input file not found
    """
    logger.info("Starting ingest node")

    input_path = state.get("input_path")
    if not input_path:
        raise ValueError("input_path not provided in state")

    # Read and parse file
    file_content = read_file(input_path)

    logger.info(
        f"Ingested {file_content.get('type')} file: {input_path}"
    )

    return {
        "file_content": file_content,
        "processing_log": ["Ingest completed"],
    }


def segment_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """GraphFlow node for chapter segmentation.

    Extracts chapters from the ingested document using format-specific logic.

    Args:
        state: Current graph state containing 'file_content'

    Returns:
        Update dict with 'chapters' list of chapter dictionaries

    Raises:
        ValueError: If file_content is missing or malformed
    """
    logger.info("Starting segment node")

    file_content = state.get("file_content")
    if not file_content:
        raise ValueError("file_content not available in state")

    # Extract chapters based on file type
    if file_content.get("type") == "pdf":
        chapters = segment_pages_into_chapters(file_content.get("pages", []))
        logger.info(f"Segmented PDF into {len(chapters)} chapters")
    else:
        # Default to markdown/text segmentation
        chapters = segment_text_into_chapters(file_content.get("text", ""))
        logger.info(f"Segmented text into {len(chapters)} chapters")

    # Ensure chapters have IDs (fallback to index if missing)
    for idx, chapter in enumerate(chapters):
        if "id" not in chapter:
            chapter["id"] = f"chapter_{idx}"

    return {
        "chapters": chapters,
        "processing_log": ["Segment completed"],
    }


def script_gen_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """GraphFlow node for script generation with per-chapter checkpoint support.

    Supports both sequential and parallel execution based on environment variables.
    When MAX_WORKERS > 1, uses ThreadPoolExecutor for parallelization.

    With per-chapter checkpointing (Phase 4):
    - Checks which chapters have already been processed
    - Only processes new/pending chapters
    - Resumes from checkpoint if available
    - Loads pre-generated scripts for completed chapters

    Args:
        state: Current graph state containing 'chapters' and optionally 'chapter_index'

    Returns:
        Update dict with 'script_gen' containing generated scripts

    Raises:
        ValueError: If chapters not available in state
    """
    logger.info("Starting script generation node")

    chapters = state.get("chapters", [])
    if not chapters:
        raise ValueError("No chapters available in state")

    # Check if we're in parallel mode (chapter_index set) or normal mode
    chapter_index = state.get("chapter_index")

    if chapter_index is not None:
        # Single chapter mode (used by parallel workers)
        logger.debug(f"Processing single chapter at index {chapter_index}")
        chapter = chapters[chapter_index]
        return _generate_single_script(chapter, state, chapter_index)
    else:
        # Normal dispatcher mode: check parallelization settings
        try:
            max_workers = int(os.getenv("MAX_WORKERS", "1"))
        except Exception:
            max_workers = 1

        # Phase 4: Check for completed chapters from checkpoint
        run_id = state.get("run_id")
        completed_chapter_ids = []
        if run_id:
            try:
                completed_chapter_ids = get_completed_chapters(run_id)
            except Exception as e:
                logger.warning(f"Could not load completed chapters: {e}")

        # Filter out already-completed chapters
        chapters_to_process = []
        chapters_to_skip = []
        for chapter in chapters:
            chapter_id = chapter.get("id", "")
            if chapter_id in completed_chapter_ids:
                chapters_to_skip.append(chapter)
            else:
                chapters_to_process.append(chapter)

        if chapters_to_skip:
            logger.info(
                f"Skipping {len(chapters_to_skip)} already-completed chapters"
            )

        # Process remaining chapters
        if chapters_to_process:
            if max_workers > 1 and len(chapters_to_process) > 1:
                logger.info(
                    f"Using parallel script generation with {max_workers} workers "
                    f"for {len(chapters_to_process)} chapters"
                )
                script_results = _generate_scripts_parallel_threaded(
                    chapters_to_process, state, max_workers
                )
            else:
                logger.info(
                    f"Using sequential script generation for {len(chapters_to_process)} chapters"
                )
                script_results = _generate_scripts_sequential(chapters_to_process, state)
        else:
            script_results = []

        # Load pre-generated scripts for skipped chapters
        if chapters_to_skip and run_id:
            logger.debug("Loading pre-generated scripts for completed chapters")
            for chapter in chapters_to_skip:
                chapter_id = chapter.get("id", "")
                try:
                    # Load from checkpoint
                    from .runs_checkpoint import load_chapter_checkpoint
                    chapter_data = load_chapter_checkpoint(run_id, chapter_id)
                    if chapter_data and chapter_data.get("status") == "completed":
                        result = chapter_data.get("result")
                        if result:
                            script_results.append(result)
                except Exception as e:
                    logger.warning(
                        f"Could not load cached script for {chapter_id}: {e}"
                    )

        return {
            "script_gen": script_results,
            "run_id": state.get("run_id"),
            "llm_adapter_used": state.get("llm_adapter_used", "unknown"),
            "processing_log": [
                f"Script generation completed "
                f"({len(chapters_to_process)} new, {len(chapters_to_skip)} from cache)"
            ],
        }


def _generate_single_script(
    chapter: Dict[str, Any], state: Dict[str, Any], index: int
) -> Dict[str, Any]:
    """Generate script for a single chapter with per-chapter checkpoint support.

    Phase 4 Enhancement: Saves checkpoint after each chapter is processed.

    Args:
        chapter: Chapter dictionary
        state: Current state (contains adapter and run_id)
        index: Chapter index

    Returns:
        Update dict with single script in list
    """
    google = state.get("google")
    if google is None:
        google = GoogleServices()

    run_id = state.get("run_id", str(uuid.uuid4()))
    chapter_id = chapter.get("id", f"chapter_{index}")

    try:
        logger.debug(f"Generating script for chapter {index}: {chapter_id}")
        script = generate_slides_for_chapter(chapter, google, run_id=run_id)
        
        # Phase 4: Save per-chapter checkpoint
        if run_id:
            save_chapter_checkpoint(
                run_id,
                chapter_id,
                status="completed",
                result=script,
            )
        
        logger.debug(f"Generated script for chapter {index}: {chapter_id}")
        return {
            "script_gen": [script],  # Return as list for reducer to extend
            "processing_log": [f"Script for chapter {index} generated"],
        }
    except Exception as e:
        logger.error(f"Error generating script for chapter {index}: {e}")
        
        # Phase 4: Save failure checkpoint
        if run_id:
            save_chapter_checkpoint(
                run_id,
                chapter_id,
                status="failed",
                error=str(e),
            )
        
        return {
            "errors": [{"chapter_index": index, "error": str(e)}],
            "processing_log": [f"Error generating script for chapter {index}"],
        }


def _generate_scripts_parallel(
    chapters: List[Dict[str, Any]],
    adapter: Any,
    run_id: str,
    max_workers: int,
    rate_limit: Optional[float],
) -> List[Dict[str, Any]]:
    """Generate scripts for chapters in parallel (DEPRECATED - use graph-based parallelization).

    This function is kept for backward compatibility but the graph now handles
    parallelization directly via the engine.

    Args:
        chapters: List of chapter dictionaries
        adapter: LLM adapter instance
        run_id: Run identifier for tracking
        max_workers: Number of parallel workers
        rate_limit: Optional rate limit in requests per second

    Returns:
        List of generated script dictionaries
    """
    logger.warning("Direct parallel generation called - use graph parallelization instead")

    def make_task(chapter):
        def _task():
            return generate_slides_for_chapter(chapter, adapter, run_id=run_id)

        return _task

    tasks = [make_task(c) for c in chapters]

    # Run tasks in parallel
    script_results = run_tasks_in_threads(
        tasks, max_workers=max_workers, rate_limit=rate_limit
    )

    return script_results


def _generate_scripts_sequential(
    chapters: List[Dict[str, Any]], state: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """Generate scripts for chapters sequentially with per-chapter checkpoint support.

    Phase 4 Enhancement: Saves checkpoint after each chapter is processed.

    Args:
        chapters: List of chapter dictionaries
        state: Current state (contains adapter and run_id)

    Returns:
        List of generated script dictionaries
    """
    google = state.get("google")
    if google is None:
        google = GoogleServices()

    run_id = state.get("run_id", str(uuid.uuid4()))

    script_results = []
    for i, chapter in enumerate(chapters):
        chapter_id = chapter.get("id", f"chapter_{i}")
        logger.debug(
            f"Generating script for chapter {i + 1}/{len(chapters)}: {chapter_id}"
        )
        
        try:
            script = generate_slides_for_chapter(chapter, google, run_id=run_id)
            script_results.append(script)
            
            # Phase 4: Save per-chapter checkpoint after each successful generation
            if run_id:
                save_chapter_checkpoint(
                    run_id,
                    chapter_id,
                    status="completed",
                    result=script,
                )
        except Exception as e:
            logger.error(f"Error generating script for chapter {i}: {e}")
            
            # Phase 4: Save failure checkpoint
            if run_id:
                save_chapter_checkpoint(
                    run_id,
                    chapter_id,
                    status="failed",
                    error=str(e),
                )
            
            # Re-raise to stop processing on first error
            raise

    return script_results


def _generate_scripts_parallel_threaded(
    chapters: List[Dict[str, Any]], state: Dict[str, Any], max_workers: int
) -> List[Dict[str, Any]]:
    """Generate scripts for chapters in parallel using ThreadPoolExecutor.

    Args:
        chapters: List of chapter dictionaries
        state: Current state (contains adapter and run_id)
        max_workers: Number of parallel workers

    Returns:
        List of generated script dictionaries
    """
    google = state.get("google")
    if google is None:
        google = GoogleServices()

    run_id = state.get("run_id", str(uuid.uuid4()))

    try:
        rate_limit = float(os.getenv("LLM_RATE_LIMIT", "0"))
        if rate_limit <= 0:
            rate_limit = None
    except Exception:
        rate_limit = None

    def make_task(chapter):
        def _task():
            return generate_slides_for_chapter(chapter, google, run_id=run_id)

        return _task

    tasks = [make_task(c) for c in chapters]

    # Use existing thread pool executor
    script_results = run_tasks_in_threads(
        tasks, max_workers=max_workers, rate_limit=rate_limit
    )

    return script_results


def compose_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """GraphFlow node for video composition.

    Composes individual chapter videos from generated scripts. Currently
    a placeholder that prepares data for composition.

    Args:
        state: Current graph state

    Returns:
        Update dict with composition tracking data

    Note:
        Full composition is currently handled separately in CLI for efficiency.
        This node exists for graph completeness and future integration.
    """
    logger.info("Starting compose node")

    scripts = state.get("scripts", [])
    num_scripts = len(scripts)

    logger.info(f"Compose node processing {num_scripts} scripts")

    return {
        "composition_ready": True,
        "num_scripts_for_composition": num_scripts,
        "processing_log": ["Compose node completed"],
    }


def merge_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """GraphFlow node for final video merge.

    Placeholder for merging composed videos into final output.

    Args:
        state: Current graph state

    Returns:
        Update dict marking merge completion

    Note:
        Full merge is currently handled separately in CLI for efficiency.
        This node exists for graph completeness and future integration.
    """
    logger.info("Starting merge node")

    return {
        "merge_ready": True,
        "processing_log": ["Merge node completed"],
    }


# ============================================================================
# Test Helper Functions (formerly in langgraph_nodes.py)
# ============================================================================


def build_graph_description(input_path: str) -> Dict[str, Any]:
    """Return a JSON-serializable description of the pipeline graph.

    Used for testing and validation. The actual execution uses GraphFlow nodes.

    Args:
        input_path: Path to input file

    Returns:
        Dictionary describing graph nodes and edges
    """
    nodes = [
        {"id": "ingest", "type": "ingest", "config": {"path": input_path}},
        {"id": "segment", "type": "segment", "config": {}},
        {"id": "script_gen", "type": "script_generator", "config": {"adapter": "vertex"}},
    ]
    edges = [("ingest", "segment"), ("segment", "script_gen")]
    return {"nodes": nodes, "edges": edges}


def run_graph_description(desc: Dict[str, Any], llm_adapter=None, resume_run_id: str | None = None) -> Dict[str, Any]:
    """Execute graph from description.

    Tests can call this to validate graph structure and execution.
    Supports resuming from checkpoints.

    Args:
        desc: Graph description dict from build_graph_description()
        llm_adapter: Optional LLM adapter to use
        resume_run_id: Optional run ID to resume

    Returns:
        Results dict with ingest, segment, script_gen keys
    """
    nodes_dict = {n["id"]: n for n in desc.get("nodes", [])}
    ingest_cfg = nodes_dict.get("ingest", {}).get("config", {})
    path = ingest_cfg.get("path")

    run_id = resume_run_id or str(uuid.uuid4())

    # Try to load checkpoint if resuming
    checkpoint = {}
    if resume_run_id:
        try:
            from .runs import load_checkpoint
            checkpoint = load_checkpoint(run_id)
        except Exception:
            pass

    # Create initial state
    state = {
        "input_path": path,
        "llm_adapter": llm_adapter,
        "run_id": run_id,
    }

    # Execute nodes manually
    if checkpoint.get("ingest"):
        state["file_content"] = checkpoint.get("ingest")
    else:
        try:
            update = ingest_node(state)
            state.update(update)
        except Exception as e:
            return {"error": f"Ingest failed: {e}"}

    if checkpoint.get("segment"):
        state["chapters"] = checkpoint.get("segment")
    else:
        try:
            update = segment_node(state)
            state.update(update)
        except Exception as e:
            return {"error": f"Segment failed: {e}"}

    if checkpoint.get("script_gen"):
        state["script_gen"] = checkpoint.get("script_gen")
    else:
        try:
            update = script_gen_node(state)
            state.update(update)
        except Exception as e:
            return {"error": f"Script generation failed: {e}"}

    return {
        "ingest": state.get("file_content"),
        "segment": state.get("chapters"),
        "script_gen": state.get("script_gen", []),
        "run_id": state.get("run_id"),
        "llm_adapter_used": state.get("llm_adapter_used", "unknown"),
    }
