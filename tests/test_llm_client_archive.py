import os
from agent.llm_client import LLMClient


def test_archive_attempts_to_storage(tmp_path, dummy_storage):
    # Prepare a fake out_dir with attempt files
    out_dir = tmp_path / "llm_out"
    (out_dir / "run1" / "chapter-01").mkdir(parents=True)
    base = out_dir / "run1" / "chapter-01"
    (base / "attempt_01_prompt.txt").write_text("prompt")
    (base / "attempt_01_response.txt").write_text("response")
    (base / "attempt_01_validation.json").write_text("{}")

    storage = dummy_storage
    client = LLMClient(max_retries=1, out_dir=str(out_dir), storage_adapter=storage)
    # Archive
    client.archive_attempts_to_storage("run1", "chapter-01")

    # Ensure uploaded indicator files exist
    uploaded_dir = tmp_path / "storage" / "run1" / "chapter-01"
    assert any(p.name.endswith(".txt") or p.name.endswith(".json") for p in uploaded_dir.iterdir())
