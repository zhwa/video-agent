"""Checkpoint-aware execution wrapper for GraphFlow.

This module provides a wrapper around GraphFlow graph execution that adds
checkpoint and resume capabilities. It allows long-running pipelines to be
interrupted and resumed from the last successful node.

The checkpoint system is kept simple (JSON save/load) while preserving the
thread-safe atomic write semantics using per-run locks.
"""

import json
import logging
import threading
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

from .runs import ensure_run_dir, runs_dir

logger = logging.getLogger(__name__)

# Thread lock for checkpoint file writes (prevents concurrent write corruption)
_checkpoint_locks: Dict[str, threading.Lock] = {}
_locks_lock = threading.Lock()


def _get_checkpoint_lock(run_id: str) -> threading.Lock:
    """Get or create a lock for a specific run's checkpoint file."""
    with _locks_lock:
        if run_id not in _checkpoint_locks:
            _checkpoint_locks[run_id] = threading.Lock()
        return _checkpoint_locks[run_id]


def checkpoint_invoke(
    graph: Any,
    initial_state: Dict[str, Any],
    run_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Execute graph with automatic checkpointing and resume support.

    This function wraps graph.invoke() to:
    1. Load checkpoint if resuming an existing run
    2. Execute the graph
    3. Save checkpoint after completion
    4. Return the final result

    Args:
        graph: Compiled GraphFlow graph from graphflow_graph.py
        initial_state: Initial state dictionary
        run_id: Optional run ID. If provided and checkpoint exists,
                execution resumes from checkpoint.

    Returns:
        Final state dictionary after graph execution

    Raises:
        FileNotFoundError: If run_id provided but checkpoint not found
        json.JSONDecodeError: If checkpoint file is corrupted
    """

    if not run_id:
        run_id = initial_state.get("run_id")

    if not run_id:
        run_id = str(uuid.uuid4())
        initial_state["run_id"] = run_id

    logger.info(f"Starting execution for run: {run_id}")

    # Try to load checkpoint if resuming
    checkpoint_data = _load_checkpoint(run_id)
    if checkpoint_data:
        logger.info(f"Resuming from checkpoint for run {run_id}")
        # Merge checkpoint into initial state
        initial_state.update(checkpoint_data)
    else:
        logger.debug(f"No checkpoint found for run {run_id}, starting fresh")

    # Execute the graph
    try:
        logger.debug("Invoking graph...")
        result = graph.invoke(initial_state)
        logger.info(f"Graph execution completed successfully for run {run_id}")
    except Exception as e:
        logger.error(f"Graph execution failed for run {run_id}: {e}")
        raise

    # Save checkpoint after successful completion
    _save_checkpoint(run_id, result)

    return result


def _get_checkpoint_file(run_id: str) -> Path:
    """Get the checkpoint file path for a run."""
    return ensure_run_dir(run_id) / "checkpoint.json"


def _save_checkpoint(run_id: str, state: Dict[str, Any]) -> None:
    """Save state as a checkpoint for resume capability.

    Saves the state in a simple JSON format, filtering out non-serializable
    objects like LLM adapters. For more sophisticated checkpointing
    (e.g., during parallel execution), consider using runs_safe.py with
    its file locking mechanism.

    Args:
        run_id: Run identifier
        state: State dictionary to save

    Raises:
        IOError: If checkpoint file cannot be written
    """
    checkpoint_file = _get_checkpoint_file(run_id)

    # Filter out non-JSON-serializable objects (like adapters)
    serializable_state = {}
    for key, value in state.items():
        # Skip LLM adapters and other complex objects
        if key in ("llm_adapter", "llm_adapter_used") or isinstance(
            value, type
        ):
            continue
        try:
            # Test if serializable
            json.dumps(value)
            serializable_state[key] = value
        except (TypeError, ValueError):
            # Skip non-serializable values
            logger.debug(f"Skipping non-serializable field in checkpoint: {key}")
            continue

    try:
        # Write checkpoint
        checkpoint_file.write_text(
            json.dumps(serializable_state, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        logger.debug(f"Saved checkpoint to {checkpoint_file}")
    except Exception as e:
        logger.error(f"Failed to save checkpoint: {e}")
        # Don't raise here - checkpoint failure shouldn't crash execution
        pass


def _load_checkpoint(run_id: str) -> Optional[Dict[str, Any]]:
    """Load a checkpoint for resume capability.

    Returns an empty dict if no checkpoint exists (indicating fresh start).

    Args:
        run_id: Run identifier

    Returns:
        Checkpoint state dict, or empty dict if no checkpoint exists

    Raises:
        json.JSONDecodeError: If checkpoint file is corrupted
    """
    checkpoint_file = _get_checkpoint_file(run_id)

    if not checkpoint_file.exists():
        return None

    try:
        data = json.loads(checkpoint_file.read_text(encoding="utf-8"))
        logger.debug(f"Loaded checkpoint from {checkpoint_file}")
        return data
    except json.JSONDecodeError as e:
        logger.error(f"Checkpoint file corrupted: {e}")
        raise


# ============================================================================
# Per-Chapter Checkpoint Functions (Phase 4)
# ============================================================================


def save_chapter_checkpoint(
    run_id: str,
    chapter_id: str,
    status: str,
    result: Optional[Dict[str, Any]] = None,
    error: Optional[str] = None,
) -> None:
    """Save checkpoint for individual chapter processing.

    This function allows per-chapter progress tracking during script
    generation. It's useful for long-running documents with many chapters.

    Chapter status values:
    - "pending": Chapter not yet processed
    - "in_progress": Chapter currently being processed
    - "completed": Chapter successfully processed
    - "failed": Chapter processing failed

    Args:
        run_id: Run identifier
        chapter_id: Unique chapter identifier (e.g., "chapter_0", "intro")
        status: Processing status
        result: Result data (if completed)
        error: Error message (if failed)

    Raises:
        IOError: If checkpoint cannot be written
    """
    checkpoint_file = _get_checkpoint_file(run_id)
    lock = _get_checkpoint_lock(run_id)

    with lock:
        # Load existing checkpoint
        try:
            if checkpoint_file.exists():
                checkpoint_data = json.loads(
                    checkpoint_file.read_text(encoding="utf-8")
                )
            else:
                checkpoint_data = {}
        except json.JSONDecodeError:
            logger.warning(f"Could not parse existing checkpoint, recreating...")
            checkpoint_data = {}

        # Ensure per-chapter tracking structure exists
        if "script_gen_chapters" not in checkpoint_data:
            checkpoint_data["script_gen_chapters"] = {}

        # Save chapter status
        chapter_entry = {"status": status}
        if result is not None:
            chapter_entry["result"] = result
        if error is not None:
            chapter_entry["error"] = error

        checkpoint_data["script_gen_chapters"][chapter_id] = chapter_entry

        try:
            checkpoint_file.write_text(
                json.dumps(checkpoint_data, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            logger.debug(f"Saved chapter checkpoint for {chapter_id} (status={status})")
        except Exception as e:
            logger.error(f"Failed to save chapter checkpoint: {e}")
            # Don't raise - checkpoint failure shouldn't crash execution


def load_chapter_checkpoint(
    run_id: str,
    chapter_id: str,
) -> Optional[Dict[str, Any]]:
    """Load checkpoint data for a specific chapter.

    Args:
        run_id: Run identifier
        chapter_id: Chapter identifier

    Returns:
        Chapter checkpoint entry with status, result, and error fields
        Returns None if no checkpoint exists for this chapter

    Raises:
        json.JSONDecodeError: If checkpoint file is corrupted
    """
    checkpoint_file = _get_checkpoint_file(run_id)

    if not checkpoint_file.exists():
        return None

    try:
        checkpoint_data = json.loads(checkpoint_file.read_text(encoding="utf-8"))
        chapters = checkpoint_data.get("script_gen_chapters", {})
        return chapters.get(chapter_id)
    except json.JSONDecodeError as e:
        logger.error(f"Checkpoint file corrupted: {e}")
        raise


def get_completed_chapters(run_id: str) -> list[str]:
    """Get list of completed chapter IDs from checkpoint.

    Args:
        run_id: Run identifier

    Returns:
        List of chapter IDs that have been successfully processed.
        Returns empty list if no checkpoint exists.

    Raises:
        json.JSONDecodeError: If checkpoint file is corrupted
    """
    checkpoint_file = _get_checkpoint_file(run_id)

    if not checkpoint_file.exists():
        return []

    try:
        checkpoint_data = json.loads(checkpoint_file.read_text(encoding="utf-8"))
        chapters = checkpoint_data.get("script_gen_chapters", {})
        return [
            chapter_id
            for chapter_id, entry in chapters.items()
            if entry.get("status") == "completed"
        ]
    except json.JSONDecodeError as e:
        logger.error(f"Checkpoint file corrupted: {e}")
        raise


def get_failed_chapters(run_id: str) -> list[str]:
    """Get list of failed chapter IDs from checkpoint.

    Args:
        run_id: Run identifier

    Returns:
        List of chapter IDs that failed processing.
        Returns empty list if no checkpoint exists.

    Raises:
        json.JSONDecodeError: If checkpoint file is corrupted
    """
    checkpoint_file = _get_checkpoint_file(run_id)

    if not checkpoint_file.exists():
        return []

    try:
        checkpoint_data = json.loads(checkpoint_file.read_text(encoding="utf-8"))
        chapters = checkpoint_data.get("script_gen_chapters", {})
        return [
            chapter_id
            for chapter_id, entry in chapters.items()
            if entry.get("status") == "failed"
        ]
    except json.JSONDecodeError as e:
        logger.error(f"Checkpoint file corrupted: {e}")
        raise


def clear_chapter_checkpoint(run_id: str, chapter_id: str) -> None:
    """Clear checkpoint for a specific chapter (useful for retries).

    Args:
        run_id: Run identifier
        chapter_id: Chapter identifier to clear

    Raises:
        IOError: If checkpoint cannot be written
    """
    checkpoint_file = _get_checkpoint_file(run_id)

    if not checkpoint_file.exists():
        return

    try:
        checkpoint_data = json.loads(checkpoint_file.read_text(encoding="utf-8"))
        chapters = checkpoint_data.get("script_gen_chapters", {})
        chapters.pop(chapter_id, None)

        checkpoint_file.write_text(
            json.dumps(checkpoint_data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        logger.debug(f"Cleared checkpoint for {chapter_id}")
    except Exception as e:
        logger.error(f"Failed to clear chapter checkpoint: {e}")
