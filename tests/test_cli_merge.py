import sys
import types
import json
from pathlib import Path
from agent.cli import main as cli_main


def test_cli_merge_flow(tmp_path, monkeypatch):
    # Prepare a markdown with 2 chapters
    md = tmp_path / "lesson.md"
    md.write_text("# Chapter 1\n\nOne.\n# Chapter 2\n\nTwo.")

    # Fake LLM
    google = types.ModuleType("google")
    generativeai = types.ModuleType("google.generativeai")
    def fake_generate_text(model, input):
        return types.SimpleNamespace(candidates=[types.SimpleNamespace(output='{"slides": [{"id": "s01","title": "T","bullets":["a"], "visual_prompt":"v","estimated_duration_sec":1, "speaker_notes":"n"}]}')])
    generativeai.generate_text = fake_generate_text
    google.generativeai = generativeai
    sys.modules["google"] = google
    sys.modules["google.generativeai"] = generativeai

    # configure providers
    monkeypatch.setenv("TTS_PROVIDER", "dummy")
    monkeypatch.setenv("IMAGE_PROVIDER", "dummy")
    monkeypatch.setenv("STORAGE_PROVIDER", "dummy")
    monkeypatch.setenv("LLM_OUT_DIR", str(tmp_path / "out"))

    # monkeypatch composition to write placeholder files
    import agent.video_composer as vc
    def fake_compose(self, slides, run_id, chapter_id, upload_path=None):
        path = str(tmp_path / f"chapter_{chapter_id}.mp4")
        with open(path, "wb") as f:
            f.write(b"MP4")
        return {"video_url": f"file://{path}"}

    monkeypatch.setattr(vc.VideoComposer, "compose_and_upload_chapter_video", fake_compose)

    # monkeypatch merge to just write a placeholder
    def fake_merge(self, urls, out_path, transition_sec=0.0):
        with open(out_path, "wb") as f:
            f.write(b"MERGED")
        return out_path

    monkeypatch.setattr(vc.VideoComposer, "merge_videos", fake_merge)

    argv = ["prog", str(md), "--out", str(tmp_path / 'out'), "--provider", "vertex", "--compose", "--merge"]
    monkeypatch.setattr(sys, "argv", argv)
    cli_main()

    # Verify the course output exists (local file)
    course = tmp_path / "out" / (md.stem + "_course.mp4")
    assert course.exists()

    # cleanup
    del sys.modules["google.generativeai"]
    del sys.modules["google"]