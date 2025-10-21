from agent.script_generator import generate_slides_for_chapter
from agent.adapters.llm import DummyLLMAdapter
from agent.storage import get_storage_adapter
import os


def test_pipeline_generates_audio_and_images(tmp_path, monkeypatch):
    # Use dummy adapters by default
    monkeypatch.setenv("TTS_PROVIDER", "dummy")
    monkeypatch.setenv("IMAGE_PROVIDER", "dummy")
    monkeypatch.setenv("STORAGE_PROVIDER", "dummy")
    monkeypatch.setenv("LLM_OUT_DIR", str(tmp_path / "out"))

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
        assert s["audio_url"].startswith("file://")
        assert "image_url" in s
        assert s["image_url"].startswith("file://")