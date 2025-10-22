import sys
import types
import json
import pytest
import os
from pathlib import Path
from agent.cli import main as cli_main


@pytest.mark.skipif(
    not os.getenv("GOOGLE_API_KEY") and not os.getenv("GOOGLE_GENAI_API_KEY"),
    reason="Google API key required for integration test"
)
def test_cli_compose_attaches_videos(tmp_path, monkeypatch):
    # Prepare a simple markdown file
    md = tmp_path / "lesson.md"
    md.write_text("# Title\nA short paragraph. Another sentence.")

    # Fake the Vertex generativeai module to return JSON
    google = types.ModuleType("google")
    generativeai = types.ModuleType("google.generativeai")

    class FakeResp:
        def __init__(self, output: str):
            self.candidates = [types.SimpleNamespace(output=output)]

    def fake_generate_text(model, input):
        return FakeResp('[{"slides": [{"id": "s01","title": "T","bullets":["a"], "visual_prompt":"v","estimated_duration_sec":30, "speaker_notes":"n"}]}]')

    generativeai.generate_text = fake_generate_text
    google.generativeai = generativeai
    sys.modules["google"] = google
    sys.modules["google.generativeai"] = generativeai

    # Configure providers
    monkeypatch.setenv("TTS_PROVIDER", "dummy")
    monkeypatch.setenv("IMAGE_PROVIDER", "dummy")
    monkeypatch.setenv("STORAGE_PROVIDER", "dummy")
    monkeypatch.setenv("LLM_OUT_DIR", str(tmp_path / "out"))

    # Monkeypatch composer to avoid moviepy dependency
    import agent.video_composer as vc

    def fake_compose(self, slides, run_id, chapter_id, upload_path=None):
        return {"video_url": f"file://{str(tmp_path / (chapter_id + '.mp4'))}", "srt_url": f"file://{str(tmp_path / (chapter_id + '.srt'))}"}

    monkeypatch.setattr(vc.VideoComposer, "compose_and_upload_chapter_video", fake_compose)

    # Run CLI
    argv = ["prog", str(md), "--out", str(tmp_path / 'out'), "--compose"]
    monkeypatch.setattr(sys, "argv", argv)
    cli_main()

    # Check results file
    out_file = tmp_path / "out" / (md.stem + "_results.json")
    assert out_file.exists()
    data = json.loads(out_file.read_text(encoding='utf-8'))
    for chap in data.get("script_gen", []):
        assert "composition" in chap
        assert "video_url" in chap["composition"]

    # Clean up
    del sys.modules["google.generativeai"]
    del sys.modules["google"]