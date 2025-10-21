import sys
from pathlib import Path
from agent.cli import main as cli_main
from agent.runs import create_run, save_checkpoint
from agent.langgraph_nodes import build_graph_description
import types


def test_cli_compose_resumes(tmp_path, monkeypatch):
    md = tmp_path / "lesson.md"
    md.write_text("# Chapter 1\nOne.\n# Chapter 2\nTwo.")

    # Fake generate slides and save script_gen checkpoint (two chapters)
    desc = build_graph_description(str(md))
    # save checkpoint with script_gen for two chapters
    run_id = create_run(str(md), run_id="resume-test")
    script_gen = [
        {"chapter_id": "chapter-01", "slides": [{"id": "s01"}]},
        {"chapter_id": "chapter-02", "slides": [{"id": "s01"}]} ,
    ]
    save_checkpoint(run_id, "script_gen", script_gen)

    # Pre-mark chapter-01 as already composed
    composition = [{"chapter_id": "chapter-01", "video_url": "file://already.mp4"}]
    save_checkpoint(run_id, "composition", composition)

    # Provide a fake composer that will fail the test if called for chapter-01
    import agent.video_composer as vc

    def fake_compose(self, slides, run_id_arg, chapter_id, upload_path=None):
        if chapter_id == "chapter-01":
            raise AssertionError("Should not recompose already composed chapter")
        return {"video_url": f"file://{chapter_id}.mp4"}

    monkeypatch.setattr(vc.VideoComposer, "compose_and_upload_chapter_video", fake_compose)

    # Run CLI with --resume to use our pre-existing run_id
    argv = ["prog", str(md), "--out", str(tmp_path / 'out'), "--resume", run_id, "--compose"]
    monkeypatch.setattr(sys, "argv", argv)
    cli_main()
