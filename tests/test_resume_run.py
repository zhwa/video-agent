from agent.graphflow_nodes import build_graph_description, run_graph_description
from agent.runs import create_run, save_checkpoint
from pathlib import Path


def test_resume_uses_checkpoint(tmp_path):
    md = tmp_path / "doc.md"
    md.write_text("# Title\nOriginal text")

    run_id = create_run(str(md), run_id="test-run")
    # save ingest checkpoint to override file content
    ingest_data = {"type": "markdown", "text": "CHECKPOINTED TEXT"}
    save_checkpoint(run_id, "ingest", ingest_data)

    desc = build_graph_description(str(md))
    result = run_graph_description(desc, resume_run_id=run_id)
    assert result["ingest"]["text"] == "CHECKPOINTED TEXT"
