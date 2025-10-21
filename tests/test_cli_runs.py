import sys
from pathlib import Path
from agent.cli import main as cli_main
from agent.runs import create_run
import json


def test_cli_list_and_inspect(tmp_path, monkeypatch, capsys):
    # Create a fake run
    md = tmp_path / "doc.md"
    md.write_text("# Test")
    run_id = create_run(str(md), run_id="run-list")

    # List runs
    argv = ["prog", str(md), "--list-runs"]
    monkeypatch.setattr(sys, "argv", argv)
    cli_main()
    captured = capsys.readouterr()
    assert "run-list" in captured.out

    # Inspect run
    argv = ["prog", str(md), "--inspect", "run-list"]
    monkeypatch.setattr(sys, "argv", argv)
    cli_main()
    captured = capsys.readouterr()
    assert "metadata" in captured.out or "path" in captured.out
