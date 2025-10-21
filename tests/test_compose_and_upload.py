import pytest
import os
from agent.video_composer import VideoComposer


def _has_moviepy() -> bool:
    try:
        from moviepy.editor import ImageClip  # noqa: F401

        return True
    except Exception:
        return False


@pytest.mark.skipif(not _has_moviepy(), reason="moviepy not installed")
def test_compose_and_upload_with_dummy_storage(tmp_path, monkeypatch):
    # Set dummy storage
    monkeypatch.setenv("STORAGE_PROVIDER", "dummy")
    monkeypatch.setenv("LLM_OUT_DIR", str(tmp_path / "out"))
    # Create dummy assets (file://)
    img = tmp_path / "img.png"
    img.write_bytes(b"\x89PNG\r\n\x1a\n" + b"image")
    audio = tmp_path / "audio.mp3"
    audio.write_bytes(b"ID3")

    slides = [
        {"image_url": f"file://{str(img)}", "audio_url": f"file://{str(audio)}", "estimated_duration_sec": 1, "speaker_notes": "Hello"}
    ]

    composer = VideoComposer()
    # Monkeypatch compose_chapter to avoid relying on moviepy in tests
    def stub_compose(self, slides, out_path, include_subtitles=True):
        # Create a placeholder mp4 and srt
        with open(out_path, "wb") as f:
            f.write(b"MP4")
        srt_path = os.path.splitext(out_path)[0] + ".srt"
        with open(srt_path, "w", encoding="utf-8") as f:
            f.write("1\n00:00:00,000 --> 00:00:01,000\nHello\n")
        return out_path

    import agent.video_composer as vc
    monkeypatch.setattr(vc.VideoComposer, "compose_chapter", stub_compose)

    res = composer.compose_and_upload_chapter_video(slides, "run1", "chapter-01")
    assert "video_url" in res
    # Dummy storage returns file:// path
    assert res["video_url"].startswith("file://") or res["video_url"].endswith('.mp4')