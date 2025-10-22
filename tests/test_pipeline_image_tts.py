from agent.script_generator import generate_slides_for_chapter
from agent.adapters.llm import DummyLLMAdapter
import os


def test_pipeline_generates_audio_and_images(tmp_path, monkeypatch, dummy_storage):
    # Use dummy adapters by default
    monkeypatch.setenv("TTS_PROVIDER", "dummy")
    monkeypatch.setenv("IMAGE_PROVIDER", "dummy")
    monkeypatch.setenv("LLM_OUT_DIR", str(tmp_path / "out"))
    
    # Mock get_storage_adapter to return our fixture
    import agent.script_generator as sg
    monkeypatch.setattr(sg, "get_storage_adapter", lambda *args, **kwargs: dummy_storage)
    import agent.video_composer as vc
    monkeypatch.setattr(vc, "get_storage_adapter", lambda *args, **kwargs: dummy_storage)

    chapter = {"id": "c01", "title": "Intro", "text": "One. Two. Three."}
    adapter = DummyLLMAdapter()
    result = generate_slides_for_chapter(chapter, adapter, max_slides=2, run_id="run1")
    assert result["chapter_id"] == "c01"
    slides = result["slides"]
    assert isinstance(slides, list)
    assert len(slides) >= 1
    # Check that each slide has audio_url and image_url keys set (file://)
    for s in slides:
        assert "audio_url" in s
        assert s["audio_url"].startswith("file://"), f"Expected file:// URL, got {s['audio_url']}"
        assert "image_url" in s
        assert s["image_url"].startswith("file://"), f"Expected file:// URL, got {s['image_url']}"