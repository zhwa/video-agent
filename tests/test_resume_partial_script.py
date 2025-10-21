from agent.langgraph_nodes import build_graph_description, run_graph_description
from agent.runs import create_run, save_checkpoint
from agent.segmenter import segment_text_into_chapters
from agent.adapters.llm import DummyLLMAdapter


def test_resume_partial_script_generation(tmp_path, monkeypatch):
    # Create markdown with two chapters
    md = tmp_path / "doc.md"
    md.write_text("# Chapter 1\n\nOne sentence. Another sentence.\n# Chapter 2\n\nTwo sentences here.")

    run_id = create_run(str(md), run_id="partial-run")
    # Save segment checkpoint so the run believes segmentation already happened
    chapters = segment_text_into_chapters(md.read_text())
    save_checkpoint(run_id, "segment", chapters)

    # Simulate that the first chapter has already been generated
    first_plan = DummyLLMAdapter().generate_slide_plan(chapters[0]["text"], run_id=run_id, chapter_id=chapters[0]["id"])
    save_checkpoint(run_id, "script_gen", [{"chapter_id": chapters[0]["id"], "slides": first_plan.get("slides")}])

    # Run with a DummyLLMAdapter so remaining chapters are generated deterministically
    result = run_graph_description(build_graph_description(str(md)), llm_adapter=DummyLLMAdapter(), resume_run_id=run_id)
    # Ensure both chapters are present in final script_gen
    assert len(result["script_gen"]) == len(chapters)
    ids = [s.get("chapter_id") for s in result["script_gen"]]
    assert chapters[0]["id"] in ids and chapters[1]["id"] in ids
