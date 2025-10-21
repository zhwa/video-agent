import os
import pytest
from agent.video_composer import VideoComposer


def _has_moviepy() -> bool:
    try:
        from moviepy.editor import ImageClip  # noqa: F401

        return True
    except Exception:
        return False


@pytest.mark.skipif(not _has_moviepy(), reason="moviepy not installed")
def test_compose_short_video(tmp_path):
    out = tmp_path / "out.mp4"
    # Create dummy image
    img = tmp_path / "img.png"
    img.parent.mkdir(parents=True, exist_ok=True)
    with open(img, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n" + b"dummy")
    # Create dummy audio (very short silence using wave)
    audio = tmp_path / "audio.mp3"
    # Use a tiny silent mp3 placeholder to avoid complex generation
    with open(audio, "wb") as f:
        f.write(b"ID3")

    slides = [
        {"image_path": str(img), "audio_path": str(audio), "estimated_duration_sec": 1, "speaker_notes": "Hello"},
        {"image_path": str(img), "audio_path": str(audio), "estimated_duration_sec": 1, "speaker_notes": "World"},
    ]

    composer = VideoComposer()
    composer.compose_chapter(slides, str(out))
    assert out.exists()
    # Subtitles should also exist
    srt = tmp_path / "out.srt"
    assert srt.exists()