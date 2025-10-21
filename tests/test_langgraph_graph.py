from agent.langgraph_graph import LectureAgentRunner
from pathlib import Path


def test_runner_on_markdown(tmp_path):
    md = tmp_path / "lesson.md"
    md.write_text("# Start\nThis is some lesson text.\n## Part A\nA1\n## Part B\nB1")
    r = LectureAgentRunner(workspace_dir=str(tmp_path))
    out = r.ingest_and_segment(str(md))
    assert str(md) in out
    chapters = out[str(md)]
    assert any("Part A" in c.get("title", "") for c in chapters)