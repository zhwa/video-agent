from agent.script_generator import generate_slides_for_chapter
import os


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
    google = MockGoogleServices()
    result = generate_slides_for_chapter(chapter, google, max_slides=2, run_id="run1")
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