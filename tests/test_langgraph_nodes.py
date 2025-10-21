from agent.langgraph_nodes import build_graph_description, run_graph_description
from pathlib import Path


def test_build_graph_description(tmp_path):
    f = tmp_path / "lesson.md"
    f.write_text("# Title\nSome content.")
    desc = build_graph_description(str(f))
    assert "nodes" in desc and "edges" in desc
    ids = [n["id"] for n in desc["nodes"]]
    assert set(["ingest", "segment", "script_gen"]).issubset(set(ids))
    # ensure the default adapter configured in the graph description is vertex
    script_node = next((n for n in desc["nodes"] if n["id"] == "script_gen"), None)
    assert script_node is not None
    assert script_node.get("config", {}).get("adapter") == "vertex"


def test_run_graph_description_md(tmp_path):
    f = tmp_path / "lesson.md"
    f.write_text("# Title\nThis is the first sentence. Second sentence here. Third sentence.")
    desc = build_graph_description(str(f))
    result = run_graph_description(desc)
    assert "ingest" in result
    assert "segment" in result
    assert "script_gen" in result
    assert isinstance(result["segment"], list)
    assert isinstance(result["script_gen"], list)
