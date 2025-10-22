import os
from agent.video_composer import VideoComposer


def test_compose_and_upload_uploads_to_storage(tmp_path, monkeypatch, dummy_storage):
    # Use fixture-provided storage
    storage = dummy_storage
    storage_dir = tmp_path / "storage"
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
        return out_path

    import agent.video_composer as vc
    monkeypatch.setattr(vc.VideoComposer, "compose_chapter", stub_compose)

    # Pass storage adapter directly by monkeypatching get_storage_adapter
    import agent.video_composer as vc
    monkeypatch.setattr(vc, "get_storage_adapter", lambda *args, **kwargs: storage)

    res = composer.compose_and_upload_chapter_video(slides, "run1", "chapter-01")
    # Should return a remote URL
    assert res.get("video_url", "").startswith("file://")
    # Uploaded file present in storage dir
    assert any(p.suffix == ".mp4" for p in storage_dir.rglob("*.mp4"))
