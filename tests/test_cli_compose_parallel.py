import sys
import types
import time
import threading
from pathlib import Path
from agent.cli import main as cli_main


def test_cli_compose_parallel_respects_max_workers(tmp_path, monkeypatch):
    # Prepare markdown with multiple small chapters
    md = tmp_path / "lesson.md"
    md.write_text("# Chapter 1\n\nOne.\n# Chapter 2\n\nTwo.\n# Chapter 3\n\nThree.")

    # Fake LLM to return slides for each chapter (we'll rely on segmenter to produce 3 chapters)
    google = types.ModuleType("google")
    generativeai = types.ModuleType("google.generativeai")

    def fake_generate_text(model, input):
        return types.SimpleNamespace(candidates=[types.SimpleNamespace(output='{"slides": [{"id": "s01","title": "T","bullets":["a"], "visual_prompt":"v","estimated_duration_sec":1, "speaker_notes":"n"}]}')])

    generativeai.generate_text = fake_generate_text
    google.generativeai = generativeai
    sys.modules["google"] = google
    sys.modules["google.generativeai"] = generativeai

    # Configure providers
    monkeypatch.setenv("TTS_PROVIDER", "dummy")
    monkeypatch.setenv("IMAGE_PROVIDER", "dummy")
    monkeypatch.setenv("STORAGE_PROVIDER", "dummy")
    monkeypatch.setenv("LLM_OUT_DIR", str(tmp_path / "out"))
    monkeypatch.setenv("MAX_COMPOSER_WORKERS", "3")

    # Monkeypatch VideoComposer.compose_and_upload_chapter_video to simulate work and track concurrency
    import agent.video_composer as vc

    counter = {"val": 0, "max": 0, "lock": threading.Lock()}

    def slow_compose(self, slides, run_id, chapter_id, upload_path=None):
        with counter["lock"]:
            counter["val"] += 1
            if counter["val"] > counter["max"]:
                counter["max"] = counter["val"]
        time.sleep(0.2)
        with counter["lock"]:
            counter["val"] -= 1
        return {"video_url": f"file://{str(tmp_path / (chapter_id + '.mp4'))}"}

    monkeypatch.setattr(vc.VideoComposer, "compose_and_upload_chapter_video", slow_compose)

    argv = ["prog", str(md), "--out", str(tmp_path / 'out'), "--provider", "vertex", "--compose", "--compose-workers", "3"]
    monkeypatch.setattr(sys, "argv", argv)
    cli_main()

    # concurrency observed should be <= 3
    assert counter["max"] <= 3

    # Clean up fake google
    del sys.modules["google.generativeai"]
    del sys.modules["google"]