from agent.script_generator import generate_slides_for_chapter


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


def test_generate_slides_basic():
    chapter = {"id": "c01", "title": "Intro", "text": "This is sentence one. This is sentence two. This is sentence three. This is sentence four."}
    google = MockGoogleServices()
    result = generate_slides_for_chapter(chapter, google, max_slides=2)
    assert result["chapter_id"] == "c01"
    slides = result["slides"]
    assert isinstance(slides, list)
    assert len(slides) >= 1
    assert "title" in slides[0]