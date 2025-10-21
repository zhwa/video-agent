from agent.storage.dummy_storage import DummyStorageAdapter
from agent.video_composer import VideoComposer
from agent.runs import create_run, get_run_metadata
import os


def test_video_artifact_recorded_in_metadata(tmp_path, monkeypatch):
    # Prepare dummy storage and set env
    storage_dir = tmp_path / "storage"
    storage = DummyStorageAdapter(base_dir=str(storage_dir))
    # Create dummy files
    img = tmp_path / "img.png"
    img.write_bytes(b"\x89PNG\r\n\x1a\n")
    audio = tmp_path / "audio.mp3"
    audio.write_bytes(b"ID3")

    slides = [{"image_url": f"file://{img}", "audio_url": f"file://{audio}", "estimated_duration_sec": 1}]

    composer = VideoComposer()
    # Monkeypatch compose_chapter to write a local file
    def stub_compose(self, slides, out_path, include_subtitles=True):
        with open(out_path, "wb") as f:
            f.write(b"MP4")
        srt_path = os.path.splitext(out_path)[0] + ".srt"
        with open(srt_path, "w", encoding="utf-8") as f:
            f.write("1\n00:00:00,000 --> 00:00:01,000\nHello\n")
        return out_path

    import agent.video_composer as vc
    monkeypatch.setattr(vc.VideoComposer, "compose_chapter", stub_compose)

    # Pass storage adapter directly by monkeypatching get_storage_adapter
    monkeypatch.setattr(vc, "get_storage_adapter", lambda *args, **kwargs: storage)

    run_id = create_run("/tmp/path", run_id="runrec")
    composer.compose_and_upload_chapter_video(slides, run_id, "chapter-01")

    meta = get_run_metadata(run_id)
    assert meta and "artifacts" in meta
    types = {a["type"] for a in meta["artifacts"]}
    assert "video" in types
