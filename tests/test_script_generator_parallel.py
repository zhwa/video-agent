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


class SlowDummyTTS:
    def __init__(self, sleep=0.2, counter=None):
        self.sleep = sleep
        self.counter = counter or {"val": 0, "max": 0, "lock": threading.Lock()}

    def synthesize(self, text, out_path=None, voice=None, language=None):
        with self.counter["lock"]:
            self.counter["val"] += 1
            if self.counter["val"] > self.counter["max"]:
                self.counter["max"] = self.counter["val"]
        time.sleep(self.sleep)
        with self.counter["lock"]:
            self.counter["val"] -= 1
        # write a small file to simulate audio
        out = out_path or "workspace/tts/slow_dummy.wav"
        os.makedirs(os.path.dirname(out), exist_ok=True)
        with open(out, "w", encoding="utf-8") as f:
            f.write(text)
        return out


class SlowDummyImage:
    def __init__(self, sleep=0.2):
        self.sleep = sleep

    def generate_image(self, prompt, out_path=None, width=512, height=512, steps=20, seed=None):
        time.sleep(self.sleep)
        out = out_path or "workspace/images/slow_dummy.png"
        os.makedirs(os.path.dirname(out), exist_ok=True)
        with open(out, "wb") as f:
            f.write(b"\x89PNG\r\n\x1a\n" + prompt.encode("utf-8")[:64])
        return out


def test_slide_parallel_generation(monkeypatch, tmp_path):
    # configure environment
    monkeypatch.setenv("TTS_PROVIDER", "dummy")
    monkeypatch.setenv("IMAGE_PROVIDER", "dummy")
    monkeypatch.setenv("STORAGE_PROVIDER", "dummy")
    monkeypatch.setenv("LLM_OUT_DIR", str(tmp_path / "out"))
    monkeypatch.setenv("MAX_SLIDE_WORKERS", "3")

    # build a fake chapter with 6 slides
    chapter = {"id": "c01", "title": "Intro", "text": "One. Two. Three."}
    google = MockGoogleServices()
    # generate slides
    result = generate_slides_for_chapter(chapter, google, max_slides=6, run_id="run-par")
    slides = result["slides"]
    assert len(slides) >= 1

    # Now monkeypatch factories to use slow adapters and re-run
    counter = {"val": 0, "max": 0, "lock": threading.Lock()}
    monkeypatch.setenv("TTS_PROVIDER", "dummy")
    monkeypatch.setenv("IMAGE_PROVIDER", "dummy")
    # Monkeypatch adapter factories to return our slow ones
    import agent.google as google_module

    monkeypatch.setattr(google_module, "get_tts_adapter", lambda p=None: SlowDummyTTS(sleep=0.2, counter=counter))
    # No get_image_adapter in google module yet, but script_generator doesn't call it as factory anymore

    # Re-run with concurrency; expect counter['max'] <= 3
    res2 = generate_slides_for_chapter(chapter, google, max_slides=6, run_id="run-par")
    assert counter["max"] <= 3
    # all slides should have audio_url and image_url
    for s in res2["slides"]:
        assert "audio_url" in s
        assert "image_url" in s