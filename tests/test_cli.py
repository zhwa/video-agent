import sys
import types
from pathlib import Path
from agent.cli import main as cli_main


def test_cli_runs_and_writes(tmp_path, monkeypatch):
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
        return FakeResp('{"slides": [{"id": "s01","title": "T","bullets":["a"], "visual_prompt":"v","estimated_duration_sec":30, "speaker_notes":"n"}]}')

    generativeai.generate_text = fake_generate_text
    google.generativeai = generativeai
    sys.modules["google"] = google
    sys.modules["google.generativeai"] = generativeai

    # Run CLI with provider override and output to tmp path
    monkeypatch.setenv("LLM_PROVIDER", "vertex")
    outdir = tmp_path / "out"
    argv = ["prog", str(md), "--out", str(outdir), "--provider", "vertex"]
    monkeypatch.setattr(sys, "argv", argv)
    cli_main()

    # Expect results file
    out_file = outdir / (md.stem + "_results.json")
    assert out_file.exists()

    # Clean up sys.modules
    del sys.modules["google.generativeai"]
    del sys.modules["google"]
