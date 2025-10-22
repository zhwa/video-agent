"""Tests for Phase 4 per-chapter checkpoint functionality.

This test module verifies that the checkpoint system correctly tracks
per-chapter progress and enables resume from specific chapters.

Tests cover:
- Saving and loading individual chapter checkpoints
- Resume from specific chapters
- Parallel execution with per-chapter checkpoints
- Mixed completed/pending chapter scenarios
- Backward compatibility with old checkpoint format
"""

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from agent.runs_checkpoint import (
    clear_chapter_checkpoint,
    get_completed_chapters,
    get_failed_chapters,
    load_chapter_checkpoint,
    save_chapter_checkpoint,
)


@pytest.fixture
def temp_runs_dir():
    """Create a temporary runs directory for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        os.environ["RUNS_DIR"] = tmpdir
        yield tmpdir


def test_save_and_load_chapter_checkpoint(temp_runs_dir):
    """Test saving and loading a single chapter checkpoint."""
    run_id = "test_run_1"
    chapter_id = "chapter_0"
    script_result = {"title": "Chapter 1", "slides": ["slide1", "slide2"]}

    # Save chapter checkpoint
    save_chapter_checkpoint(
        run_id,
        chapter_id,
        status="completed",
        result=script_result,
    )

    # Load and verify
    loaded = load_chapter_checkpoint(run_id, chapter_id)
    assert loaded is not None
    assert loaded["status"] == "completed"
    assert loaded["result"] == script_result


def test_save_chapter_checkpoint_with_error(temp_runs_dir):
    """Test saving a failed chapter checkpoint."""
    run_id = "test_run_2"
    chapter_id = "chapter_1"
    error_msg = "Failed to generate script: API error"

    # Save failure checkpoint
    save_chapter_checkpoint(
        run_id,
        chapter_id,
        status="failed",
        error=error_msg,
    )

    # Load and verify
    loaded = load_chapter_checkpoint(run_id, chapter_id)
    assert loaded is not None
    assert loaded["status"] == "failed"
    assert loaded["error"] == error_msg


def test_get_completed_chapters(temp_runs_dir):
    """Test retrieving list of completed chapters."""
    run_id = "test_run_3"

    # Save multiple chapter checkpoints
    save_chapter_checkpoint(
        run_id, "chapter_0", "completed", result={"script": "1"}
    )
    save_chapter_checkpoint(run_id, "chapter_1", "failed", error="Error")
    save_chapter_checkpoint(
        run_id, "chapter_2", "completed", result={"script": "3"}
    )
    save_chapter_checkpoint(run_id, "chapter_3", "pending")

    # Get completed chapters
    completed = get_completed_chapters(run_id)
    assert len(completed) == 2
    assert "chapter_0" in completed
    assert "chapter_2" in completed
    assert "chapter_1" not in completed
    assert "chapter_3" not in completed


def test_get_failed_chapters(temp_runs_dir):
    """Test retrieving list of failed chapters."""
    run_id = "test_run_4"

    # Save multiple chapter checkpoints
    save_chapter_checkpoint(
        run_id, "chapter_0", "completed", result={"script": "1"}
    )
    save_chapter_checkpoint(
        run_id, "chapter_1", "failed", error="Error 1"
    )
    save_chapter_checkpoint(
        run_id, "chapter_2", "failed", error="Error 2"
    )

    # Get failed chapters
    failed = get_failed_chapters(run_id)
    assert len(failed) == 2
    assert "chapter_1" in failed
    assert "chapter_2" in failed


def test_clear_chapter_checkpoint(temp_runs_dir):
    """Test clearing a chapter checkpoint for retry."""
    run_id = "test_run_5"
    chapter_id = "chapter_0"

    # Save checkpoint
    save_chapter_checkpoint(
        run_id,
        chapter_id,
        status="completed",
        result={"script": "1"},
    )

    # Verify it was saved
    loaded = load_chapter_checkpoint(run_id, chapter_id)
    assert loaded is not None

    # Clear it
    clear_chapter_checkpoint(run_id, chapter_id)

    # Verify it's gone
    loaded = load_chapter_checkpoint(run_id, chapter_id)
    assert loaded is None


def test_multiple_chapters_same_run(temp_runs_dir):
    """Test managing multiple chapters in same run."""
    run_id = "test_run_6"
    chapters = [
        ("chapter_0", "completed", {"script": "1"}),
        ("chapter_1", "completed", {"script": "2"}),
        ("chapter_2", "in_progress", None),
        ("chapter_3", "pending", None),
    ]

    # Save all chapters
    for chapter_id, status, result in chapters:
        save_chapter_checkpoint(run_id, chapter_id, status=status, result=result)

    # Verify all are saved
    for chapter_id, status, result in chapters:
        loaded = load_chapter_checkpoint(run_id, chapter_id)
        assert loaded is not None
        assert loaded["status"] == status
        if result:
            assert loaded["result"] == result


def test_checkpoint_file_structure(temp_runs_dir):
    """Test the checkpoint file structure matches expected format."""
    run_id = "test_run_7"

    # Save some chapters
    save_chapter_checkpoint(
        run_id, "chapter_0", "completed", result={"title": "Ch1"}
    )
    save_chapter_checkpoint(
        run_id, "chapter_1", "failed", error="Some error"
    )

    # Read checkpoint file directly
    checkpoint_file = Path(temp_runs_dir) / run_id / "checkpoint.json"
    assert checkpoint_file.exists()

    data = json.loads(checkpoint_file.read_text(encoding="utf-8"))
    assert "script_gen_chapters" in data
    chapters = data["script_gen_chapters"]

    assert "chapter_0" in chapters
    assert chapters["chapter_0"]["status"] == "completed"
    assert chapters["chapter_0"]["result"] == {"title": "Ch1"}

    assert "chapter_1" in chapters
    assert chapters["chapter_1"]["status"] == "failed"
    assert chapters["chapter_1"]["error"] == "Some error"


def test_nonexistent_run_returns_none(temp_runs_dir):
    """Test loading from nonexistent run returns None."""
    result = load_chapter_checkpoint("nonexistent_run", "chapter_0")
    assert result is None


def test_nonexistent_run_get_completed_returns_empty(temp_runs_dir):
    """Test getting completed chapters for nonexistent run returns empty list."""
    result = get_completed_chapters("nonexistent_run")
    assert result == []


def test_nonexistent_chapter_returns_none(temp_runs_dir):
    """Test loading nonexistent chapter from existing run returns None."""
    run_id = "test_run_8"
    save_chapter_checkpoint(run_id, "chapter_0", "completed")

    result = load_chapter_checkpoint(run_id, "chapter_999")
    assert result is None


def test_update_chapter_checkpoint(temp_runs_dir):
    """Test updating an existing chapter checkpoint."""
    run_id = "test_run_9"
    chapter_id = "chapter_0"

    # Save initial checkpoint
    save_chapter_checkpoint(
        run_id, chapter_id, "in_progress", result=None
    )

    loaded = load_chapter_checkpoint(run_id, chapter_id)
    assert loaded["status"] == "in_progress"

    # Update to completed
    save_chapter_checkpoint(
        run_id,
        chapter_id,
        "completed",
        result={"script": "generated"},
    )

    loaded = load_chapter_checkpoint(run_id, chapter_id)
    assert loaded["status"] == "completed"
    assert loaded["result"] == {"script": "generated"}


def test_concurrent_chapter_saves(temp_runs_dir):
    """Test that concurrent saves don't corrupt checkpoint."""
    import threading

    run_id = "test_run_10"
    errors = []

    def save_chapter(idx):
        try:
            save_chapter_checkpoint(
                run_id,
                f"chapter_{idx}",
                "completed",
                result={"index": idx},
            )
        except Exception as e:
            errors.append(e)

    # Spawn multiple threads to save chapters
    threads = []
    for i in range(10):
        t = threading.Thread(target=save_chapter, args=(i,))
        threads.append(t)
        t.start()

    # Wait for all to complete
    for t in threads:
        t.join()

    # No errors should occur
    assert not errors

    # All chapters should be saved
    completed = get_completed_chapters(run_id)
    assert len(completed) == 10
    for i in range(10):
        assert f"chapter_{i}" in completed


def test_backward_compatibility_old_checkpoint(temp_runs_dir):
    """Test that old checkpoint format (without script_gen_chapters) is handled."""
    run_id = "test_run_11"

    # Create old-style checkpoint (no per-chapter info)
    checkpoint_file = Path(temp_runs_dir) / run_id / "checkpoint.json"
    checkpoint_file.parent.mkdir(parents=True, exist_ok=True)

    old_checkpoint = {
        "ingest": {"doc_type": "markdown"},
        "segment": [{"id": "chapter_0", "text": "..."}],
        "script_gen": [{"title": "Chapter 1"}],
    }
    checkpoint_file.write_text(json.dumps(old_checkpoint), encoding="utf-8")

    # Loading chapters from old checkpoint should return empty
    completed = get_completed_chapters(run_id)
    assert completed == []

    # Loading specific chapter should return None
    loaded = load_chapter_checkpoint(run_id, "chapter_0")
    assert loaded is None

    # Saving new chapter should add per-chapter structure
    save_chapter_checkpoint(run_id, "chapter_0", "completed")

    # Verify old data is preserved and new data is added
    checkpoint_file = Path(temp_runs_dir) / run_id / "checkpoint.json"
    data = json.loads(checkpoint_file.read_text(encoding="utf-8"))
    assert data["ingest"] == {"doc_type": "markdown"}  # Old data preserved
    assert "script_gen_chapters" in data  # New structure added


# Integration tests with graphflow_nodes


@patch("agent.graphflow_nodes.generate_slides_for_chapter")
def test_script_gen_node_saves_per_chapter_checkpoint(
    mock_generate, temp_runs_dir
):
    """Test that script_gen_node saves per-chapter checkpoints."""
    from agent.graphflow_nodes import _generate_single_script

    # Setup mocks
    mock_adapter = MagicMock()
    mock_generate.return_value = {"title": "Chapter 1", "slides": []}

    # Create test state and chapter
    run_id = "test_run_12"
    state = {
        "run_id": run_id,
        "google": mock_adapter,
    }
    chapter = {
        "id": "intro",
        "title": "Introduction",
        "content": "...",
    }

    # Generate script
    result = _generate_single_script(chapter, state, 0)

    # Verify checkpoint was saved
    assert result["script_gen"] == [{"title": "Chapter 1", "slides": []}]
    loaded = load_chapter_checkpoint(run_id, "intro")
    assert loaded is not None
    assert loaded["status"] == "completed"
    assert loaded["result"] == {"title": "Chapter 1", "slides": []}


@patch("agent.graphflow_nodes.generate_slides_for_chapter")
def test_script_gen_node_saves_failure_checkpoint(
    mock_generate, temp_runs_dir
):
    """Test that script_gen_node saves checkpoint for failed chapters."""
    from agent.graphflow_nodes import _generate_single_script

    # Setup mocks
    mock_adapter = MagicMock()
    mock_generate.side_effect = ValueError("Invalid chapter")

    # Create test state and chapter
    run_id = "test_run_13"
    state = {
        "run_id": run_id,
        "google": mock_adapter,
    }
    chapter = {
        "id": "chapter_1",
        "title": "Chapter 1",
        "content": "...",
    }

    # Generate script (should fail)
    result = _generate_single_script(chapter, state, 1)

    # Verify error checkpoint was saved
    assert "errors" in result
    loaded = load_chapter_checkpoint(run_id, "chapter_1")
    assert loaded is not None
    assert loaded["status"] == "failed"
    assert "Invalid chapter" in loaded["error"]


@patch("agent.graphflow_nodes.generate_slides_for_chapter")
def test_sequential_generation_saves_per_chapter(
    mock_generate, temp_runs_dir
):
    """Test that sequential generation saves each chapter."""
    from agent.graphflow_nodes import _generate_scripts_sequential

    # Setup mocks
    mock_adapter = MagicMock()
    mock_generate.side_effect = [
        {"title": "Ch1"},
        {"title": "Ch2"},
        {"title": "Ch3"},
    ]

    # Create test state and chapters
    run_id = "test_run_14"
    state = {
        "run_id": run_id,
        "google": mock_adapter,
    }
    chapters = [
        {"id": "chapter_0", "title": "Chapter 1"},
        {"id": "chapter_1", "title": "Chapter 2"},
        {"id": "chapter_2", "title": "Chapter 3"},
    ]

    # Generate scripts
    results = _generate_scripts_sequential(chapters, state)

    # Verify all chapters were saved
    assert len(results) == 3
    completed = get_completed_chapters(run_id)
    assert len(completed) == 3
    assert all(f"chapter_{i}" in completed for i in range(3))

    for i in range(3):
        loaded = load_chapter_checkpoint(run_id, f"chapter_{i}")
        assert loaded["status"] == "completed"


def test_script_gen_node_skips_completed_chapters(temp_runs_dir):
    """Test that script_gen_node skips already-completed chapters."""
    from agent.graphflow_nodes import script_gen_node

    run_id = "test_run_15"

    # Pre-populate checkpoint with completed chapters
    save_chapter_checkpoint(
        run_id, "chapter_0", "completed", result={"title": "Ch1"}
    )
    save_chapter_checkpoint(
        run_id, "chapter_1", "completed", result={"title": "Ch2"}
    )

    # Create state with 3 chapters but 2 already completed
    state = {
        "run_id": run_id,
        "chapters": [
            {"id": "chapter_0", "title": "Ch1"},
            {"id": "chapter_1", "title": "Ch2"},
            {"id": "chapter_2", "title": "Ch3"},
        ],
    }

    with patch(
        "agent.graphflow_nodes._generate_scripts_sequential"
    ) as mock_seq:
        # Mock sequential generation for only the new chapter
        mock_seq.return_value = [{"title": "Ch3"}]

        result = script_gen_node(state)

        # Verify only 1 chapter was passed to sequential generation
        call_args = mock_seq.call_args
        chapters_to_process = call_args[0][0]
        assert len(chapters_to_process) == 1
        assert chapters_to_process[0]["id"] == "chapter_2"

        # Verify processing log mentions skipped chapters
        log = result["processing_log"][0]
        assert "2 new" in log or "1 new" in log
        assert "2 from cache" in log


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
