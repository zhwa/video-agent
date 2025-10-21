import os
from agent.video_composer import VideoComposer


def test_compose_video_uses_cache(tmp_path, monkeypatch):
    monkeypatch.setenv("CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("LLM_OUT_DIR", str(tmp_path / "out"))
    slides = [{"image_url": "file:///tmp/img.png", "audio_url": "file:///tmp/audio.mp3", "estimated_duration_sec": 1}]
    composer = VideoComposer()

    call_count = {"val": 0}

    def stub_compose(self, slides, out_path, include_subtitles=True):
        call_count["val"] += 1
        with open(out_path, "wb") as f:
            f.write(b"MP4")
        return out_path

    import agent.video_composer as vc
    monkeypatch.setattr(vc.VideoComposer, "compose_chapter", stub_compose)

    # First compose will generate and cache
    res1 = composer.compose_and_upload_chapter_video(slides, "run1", "chapter-01")
    assert call_count["val"] == 1

    # Second compose (same inputs) should use cache and not call compose_chapter again
    res2 = composer.compose_and_upload_chapter_video(slides, "run1", "chapter-01")
    assert call_count["val"] == 1
