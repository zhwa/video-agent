import os
from agent.llm_client import LLMClient


def test_archive_attempts_cleanup_removes_local_files(tmp_path, monkeypatch, dummy_storage):
    # Prepare a fake out_dir with attempt files
    out_dir = tmp_path / "llm_out"
    (out_dir / "run1" / "chapter-01").mkdir(parents=True)
    base = out_dir / "run1" / "chapter-01"
    p = base / "attempt_01_prompt.txt"
    r = base / "attempt_01_response.txt"
    v = base / "attempt_01_validation.json"
    p.write_text("prompt")
    r.write_text("response")
    v.write_text("{}")

    storage = dummy_storage
    client = LLMClient(max_retries=1, out_dir=str(out_dir), storage_adapter=storage)
    # enable cleanup
    monkeypatch.setenv("LLM_ARCHIVE_CLEANUP", "true")
    client.archive_attempts_to_storage("run1", "chapter-01")

    # original attempt files should be removed
    assert not p.exists()
    assert not r.exists()
    assert not v.exists()
    # uploaded sidecar should remain
    assert (base / "attempt_01_prompt.txt.uploaded").exists()


def test_archive_cleans_local_files(tmp_path, monkeypatch, dummy_storage):
    out_dir = tmp_path / "llm_out"
    (out_dir / "run1" / "chapter-01").mkdir(parents=True)
    base = out_dir / "run1" / "chapter-01"
    f1 = base / "attempt_01_prompt.txt"
    f1.write_text("prompt")
    f2 = base / "attempt_01_response.txt"
    f2.write_text("response")

    storage = dummy_storage
    client = LLMClient(max_retries=1, out_dir=str(out_dir), storage_adapter=storage)
    monkeypatch.setenv("LLM_ARCHIVE_CLEANUP", "true")
    client.archive_attempts_to_storage("run1", "chapter-01")

    # local files should be removed
    assert not f1.exists()
    assert not f2.exists()