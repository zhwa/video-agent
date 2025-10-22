import os
import pytest
from agent.graphflow_nodes import build_graph_description, run_graph_description
from agent.runs import create_run, save_checkpoint
from pathlib import Path


@pytest.mark.skipif(
    not os.getenv("GOOGLE_API_KEY") and not os.getenv("GOOGLE_GENAI_API_KEY"),
    reason="Google API key required for integration test"
)
def test_resume_uses_checkpoint(tmp_path):
    md = tmp_path / "doc.md"
    md.write_text("# Title\nOriginal text")

    run_id = create_run(str(md), run_id="test-run")
    # save file_content checkpoint to override file content
    file_content_data = {"type": "markdown", "text": "CHECKPOINTED TEXT"}
    save_checkpoint(run_id, "file_content", file_content_data)

    desc = build_graph_description(str(md))
    result = run_graph_description(desc, resume_run_id=run_id)
    assert result["file_content"]["text"] == "CHECKPOINTED TEXT"
