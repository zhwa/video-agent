import os
import pytest
from agent.graphflow_nodes import build_graph_description, run_graph_description
from agent.runs import create_run
from agent.runs_checkpoint import save_chapter_checkpoint
from agent.segmenter import segment_text_into_chapters


class MockGoogleServices:
    """Mock Google services for testing."""
    def generate_slide_plan(self, chapter_text: str, max_slides=None, run_id=None, chapter_id=None):
        return {"slides": [{"id": "s01", "title": "Title", "bullets": ["Bullet"], "visual_prompt": "Visual", "estimated_duration_sec": 30, "speaker_notes": "Notes"}]}
    
    def synthesize_speech(self, text: str, out_path=None, voice=None, language=None):
        import os
        os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
        with open(out_path, "w") as f:
            f.write(text)
        return out_path
    
    def generate_image(self, prompt: str, out_path=None, width=1024, height=1024):
        import os
        os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
        with open(out_path, "wb") as f:
            f.write(b"\x89PNG\r\n\x1a\n" + prompt.encode("utf-8")[:64])
        return out_path


@pytest.mark.skipif(
    not os.getenv("GOOGLE_API_KEY") and not os.getenv("GOOGLE_GENAI_API_KEY"),
    reason="Google API key required for integration test"
)
def test_resume_partial_script_generation(tmp_path, monkeypatch):
    # Create markdown with two chapters
    md = tmp_path / "doc.md"
    md.write_text("# Chapter 1\n\nOne sentence. Another sentence.\n# Chapter 2\n\nTwo sentences here.")

    run_id = create_run(str(md), run_id="partial-run")
    # Save per-chapter checkpoint for the first chapter (as if it was already generated)
    chapters = segment_text_into_chapters(md.read_text())
    
    # Generate a plan for the first chapter
    google = MockGoogleServices()
    first_plan = google.generate_slide_plan(chapters[0]["text"], run_id=run_id, chapter_id=chapters[0]["id"])
    
    # Save it using per-chapter checkpoint format (Phase 4)
    save_chapter_checkpoint(
        run_id,
        chapters[0]["id"],
        status="completed",
        result={"chapter_id": chapters[0]["id"], "slides": first_plan.get("slides")},
    )

    # Run with MockGoogleServices so remaining chapters are generated deterministically
    result = run_graph_description(build_graph_description(str(md)), llm_adapter=google, resume_run_id=run_id)
    # Ensure both chapters are present in final script_gen
    assert len(result["script_gen"]) == len(chapters)
    ids = [s.get("chapter_id") for s in result["script_gen"]]
    assert chapters[0]["id"] in ids and chapters[1]["id"] in ids
