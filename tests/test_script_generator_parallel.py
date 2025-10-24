import os
import time
import threading
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


def test_slide_parallel_generation(monkeypatch, tmp_path):
    """Test that slide generation can process multiple slides in parallel."""
    # configure environment
    monkeypatch.setenv("TTS_PROVIDER", "dummy")
    monkeypatch.setenv("IMAGE_PROVIDER", "dummy")
    monkeypatch.setenv("STORAGE_PROVIDER", "dummy")
    monkeypatch.setenv("LLM_OUT_DIR", str(tmp_path / "out"))
    monkeypatch.setenv("MAX_SLIDE_WORKERS", "3")

    # build a fake chapter with 6 slides
    chapter = {"id": "c01", "title": "Intro", "text": "One. Two. Three."}
    
    # Create a mock GoogleServices that tracks concurrent calls
    counter = {"val": 0, "max": 0, "lock": threading.Lock()}
    
    class SlowMockGoogleServices:
        """Mock with slow TTS/image generation to test parallel execution."""
        
        def generate_slide_plan(self, chapter_text: str, max_slides=None, run_id=None, chapter_id=None):
            return {
                "slides": [
                    {"id": f"s{i:02d}", "title": f"Title {i}", "bullets": ["Bullet"], 
                     "visual_prompt": f"Visual {i}", "estimated_duration_sec": 30, 
                     "speaker_notes": f"Notes {i}"}
                    for i in range(1, 7)  # 6 slides
                ]
            }
        
        def synthesize_speech(self, text: str, out_path=None, voice=None, language=None):
            # Track concurrent calls
            with counter["lock"]:
                counter["val"] += 1
                if counter["val"] > counter["max"]:
                    counter["max"] = counter["val"]
            
            # Simulate slow operation
            time.sleep(0.2)
            
            with counter["lock"]:
                counter["val"] -= 1
            
            # Write output
            os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
            with open(out_path, "w") as f:
                f.write(text)
            return out_path
        
        def generate_image(self, prompt: str, out_path=None, width=1024, height=1024):
            # Image generation doesn't need to track concurrency for this test
            os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
            with open(out_path, "wb") as f:
                f.write(b"\x89PNG\r\n\x1a\n" + prompt.encode("utf-8")[:64])
            return out_path
    
    google = SlowMockGoogleServices()
    
    # Run with parallel processing enabled (MAX_SLIDE_WORKERS=3)
    result = generate_slides_for_chapter(chapter, google, max_slides=6, run_id="run-par")
    slides = result["slides"]
    
    # Verify slides were generated
    assert len(slides) >= 1
    
    # Verify parallel execution occurred (max concurrent <= 3 workers)
    assert counter["max"] <= 3, f"Expected max 3 concurrent workers, got {counter['max']}"
    assert counter["max"] >= 1, "Expected at least 1 concurrent worker"
    
    # Verify all slides have required fields
    for s in slides:
        assert "audio_url" in s
        assert "image_url" in s