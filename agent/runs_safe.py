"""Thread-safe checkpoint management for run resumption.

This module provides atomic checkpoint operations to prevent race conditions
when multiple workers save state concurrently.
"""

import json
import logging
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional
import fcntl
import tempfile

logger = logging.getLogger(__name__)


def runs_dir() -> Path:
    """Get the directory where run data is stored."""
    return Path(os.getenv("RUNS_DIR") or "workspace/runs")


def ensure_run_dir(run_id: str) -> Path:
    """Ensure run directory exists and return its path."""
    d = runs_dir() / run_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def _get_checkpoint_file(run_id: str) -> Path:
    """Get the checkpoint file path for a run."""
    return ensure_run_dir(run_id) / "checkpoint.json"


def _get_lock_file(run_id: str) -> Path:
    """Get the lock file path for a run."""
    return ensure_run_dir(run_id) / "checkpoint.lock"


def _acquire_lock(lock_file: Path, timeout: float = 5.0) -> Optional[object]:
    """
    Acquire an exclusive file lock.

    Returns a file handle if successful, None if timeout occurs.
    """
    lock_file.parent.mkdir(parents=True, exist_ok=True)
    
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            # Open file for writing, create if doesn't exist
            f = open(lock_file, 'w')
            # Try to acquire exclusive lock (non-blocking)
            try:
                fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                logger.debug("Acquired lock on %s", lock_file)
                return f
            except IOError:
                # Lock is held by another process, close and retry
                f.close()
                time.sleep(0.1)
        except Exception as e:
            logger.warning("Error acquiring lock: %s", e)
            time.sleep(0.1)
    
    logger.warning("Failed to acquire lock on %s after %.1f seconds", lock_file, timeout)
    return None


def _release_lock(lock_file_handle: object) -> None:
    """Release a file lock."""
    if lock_file_handle:
        try:
            fcntl.flock(lock_file_handle.fileno(), fcntl.LOCK_UN)
            lock_file_handle.close()
            logger.debug("Released lock")
        except Exception as e:
            logger.warning("Error releasing lock: %s", e)


def save_checkpoint_atomic(run_id: str, node: str, data: Dict) -> None:
    """
    Atomically save a checkpoint for a run node.

    Uses file locking to prevent race conditions when multiple workers
    save state concurrently.

    Args:
        run_id: The run identifier
        node: The node name (e.g., 'composition', 'script_gen')
        data: The data to checkpoint
    """
    chk_file = _get_checkpoint_file(run_id)
    lock_file = _get_lock_file(run_id)
    
    lock_handle = _acquire_lock(lock_file, timeout=5.0)
    if not lock_handle:
        logger.error("Could not acquire lock for checkpoint save, skipping")
        return
    
    try:
        # Read current checkpoint state
        if chk_file.exists():
            try:
                current = json.loads(chk_file.read_text(encoding="utf-8"))
            except json.JSONDecodeError as e:
                logger.warning("Checkpoint file corrupted, starting fresh: %s", e)
                current = {}
        else:
            current = {}
        
        # Update the specific node
        current[node] = data
        current.setdefault("completed", {})[node] = datetime.utcnow().isoformat()
        
        # Write atomically using temp file + rename
        temp_fd, temp_path = tempfile.mkstemp(
            prefix=f".{run_id}_",
            suffix=".json",
            dir=chk_file.parent
        )
        try:
            with os.fdopen(temp_fd, 'w', encoding='utf-8') as f:
                json.dump(current, f, ensure_ascii=False, indent=2)
            
            # Atomic rename (on most systems)
            os.replace(temp_path, str(chk_file))
            logger.debug("Saved checkpoint for node %s in run %s", node, run_id)
        except Exception as e:
            logger.error("Failed to write checkpoint: %s", e)
            try:
                os.unlink(temp_path)
            except Exception:
                pass
    finally:
        _release_lock(lock_handle)


def load_checkpoint(run_id: str) -> Dict:
    """
    Load the latest checkpoint for a run.

    Safe for concurrent access (uses file locking for consistency).

    Args:
        run_id: The run identifier

    Returns:
        The checkpoint dict, or empty dict if no checkpoint exists
    """
    chk_file = _get_checkpoint_file(run_id)
    if not chk_file.exists():
        return {}
    
    lock_file = _get_lock_file(run_id)
    lock_handle = _acquire_lock(lock_file, timeout=2.0)
    
    try:
        try:
            data = json.loads(chk_file.read_text(encoding="utf-8"))
            logger.debug("Loaded checkpoint from %s", chk_file)
            return data
        except json.JSONDecodeError as e:
            logger.error("Checkpoint file corrupted: %s", e)
            return {}
    finally:
        if lock_handle:
            _release_lock(lock_handle)


def get_node_checkpoint(run_id: str, node: str) -> Optional[Dict]:
    """
    Get checkpoint data for a specific node.

    Args:
        run_id: The run identifier
        node: The node name

    Returns:
        The node checkpoint data, or None if not found
    """
    checkpoint = load_checkpoint(run_id)
    return checkpoint.get(node)


def create_run(path: str, run_id: Optional[str] = None) -> str:
    """
    Create a new run with metadata.

    Args:
        path: Path to the input document
        run_id: Optional run ID (will be generated if not provided)

    Returns:
        The run ID
    """
    import uuid
    
    if not run_id:
        run_id = str(uuid.uuid4())
    
    d = ensure_run_dir(run_id)
    meta = {"path": path, "created": datetime.utcnow().isoformat(), "nodes": {}}
    meta_file = d / "metadata.json"
    meta_file.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.debug("Created run %s", run_id)
    return run_id


def get_run_metadata(run_id: str) -> Optional[Dict]:
    """
    Get metadata for a run.

    Args:
        run_id: The run identifier

    Returns:
        The metadata dict, or None if not found
    """
    d = runs_dir() / run_id
    meta_file = d / "metadata.json"
    if not meta_file.exists():
        return None
    try:
        return json.loads(meta_file.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        logger.error("Failed to read run metadata: %s", e)
        return None


def add_run_artifact(run_id: str, artifact_type: str, url: str, metadata: Optional[Dict] = None) -> None:
    """
    Add an artifact entry to the run's metadata for discovery.

    Args:
        run_id: The run identifier
        artifact_type: Type of artifact (e.g., 'video', 'tts', 'image', 'llm_attempt')
        url: URL or path to the artifact
        metadata: Optional metadata dict (chapter_id, slide_id, etc.)
    """
    d = runs_dir() / run_id
    meta_file = d / "metadata.json"
    if not meta_file.exists():
        return
    
    try:
        meta = json.loads(meta_file.read_text(encoding="utf-8"))
    except Exception as e:
        logger.warning("Failed to read metadata for artifact: %s", e)
        meta = {}
    
    meta.setdefault("artifacts", []).append({"type": artifact_type, "url": url, "metadata": metadata or {}})
    
    try:
        meta_file.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as e:
        logger.error("Failed to write artifact metadata: %s", e)


def list_runs() -> Dict:
    """
    List all available runs.

    Returns:
        Dict mapping run IDs to their metadata
    """
    d = runs_dir()
    if not d.exists():
        return {}
    
    result = {}
    try:
        for child in d.iterdir():
            if child.is_dir():
                meta = get_run_metadata(child.name)
                result[child.name] = meta
    except OSError as e:
        logger.warning("Failed to list runs: %s", e)
    
    return result
