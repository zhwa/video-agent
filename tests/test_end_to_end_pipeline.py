import os
import pytest
from agent.graphflow_nodes import build_graph_description, run_graph_description
from pathlib import Path


class MockGoogleServices:
    """Mock Google services for testing."""
    def generate_slide_plan(self, chapter_text: str, max_slides=None, run_id=None, chapter_id=None):
        # Return deterministic dummy plan
        return {"slides": [{"id": "s01", "title": "Title", "bullets": ["Bullet"], "visual_prompt": "Visual", "estimated_duration_sec": 30, "speaker_notes": "Notes"}]}
    
    def synthesize_speech(self, text: str, out_path=None, voice=None, language=None):
        # Create dummy audio file
        import os
        os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
        with open(out_path, "w") as f:
            f.write(text)
        return out_path
    
    def generate_image(self, prompt: str, out_path=None, width=1024, height=1024):
        # Create dummy image file
        import os
        os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
        with open(out_path, "wb") as f:
            f.write(b"\x89PNG\r\n\x1a\n" + prompt.encode("utf-8")[:64])
        return out_path


@pytest.mark.skipif(
    not os.getenv("GOOGLE_API_KEY") and not os.getenv("GOOGLE_GENAI_API_KEY"),
    reason="Google API key required for integration test"
)
def test_end_to_end_markdown_pipeline(tmp_path, monkeypatch, dummy_storage):
    # Create a simple markdown file
    md = tmp_path / "sample.md"
    md.write_text("# Chapter 1\n\nThis is one. This is two. This is three.", encoding="utf-8")

    # Configure dummy providers
    monkeypatch.setenv("TTS_PROVIDER", "dummy")
    monkeypatch.setenv("IMAGE_PROVIDER", "dummy")
    monkeypatch.setenv("LLM_OUT_DIR", str(tmp_path / "out"))
    
    # Mock get_storage_adapter to return our fixture
    import agent.script_generator as sg
    monkeypatch.setattr(sg, "get_storage_adapter", lambda *args, **kwargs: dummy_storage)
    import agent.video_composer as vc
    monkeypatch.setattr(vc, "get_storage_adapter", lambda *args, **kwargs: dummy_storage)

    desc = build_graph_description(str(md))
    # Use MockGoogleServices to avoid remote calls
    google = MockGoogleServices()
    result = run_graph_description(desc, llm_adapter=google)

    # Validate structure
    assert "segment" in result
    assert "script_gen" in result
    for ch_res in result["script_gen"]:
        assert "chapter_id" in ch_res
        for slide in ch_res.get("slides", []):
            assert "audio_url" in slide
            assert slide["audio_url"].startswith("file://"), f"Expected file:// URL, got {slide['audio_url']}"
            assert "image_url" in slide
            assert slide["image_url"].startswith("file://"), f"Expected file:// URL, got {slide['image_url']}"