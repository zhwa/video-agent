import pytest
import os
from agent.graphflow_nodes import build_graph_description, run_graph_description
from agent.video_composer import VideoComposer


class MockGoogleServices:
    """Mock Google services for testing."""
    def generate_slide_plan(self, chapter_text: str, max_slides=None, run_id=None, chapter_id=None):
        return {"slides": [{"id": "s01", "title": "Title", "bullets": ["Bullet"], "visual_prompt": "Visual", "estimated_duration_sec": 30, "speaker_notes": "Notes"}]}
    
    def synthesize_speech(self, text: str, out_path=None, voice=None, language=None):
        import os
        os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
        with open(out_path, "w") as f:
            f.write(text)
        return out_path
    
    def generate_image(self, prompt: str, out_path=None, width=1024, height=1024):
        import os
        os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
        with open(out_path, "wb") as f:
            f.write(b"\x89PNG\r\n\x1a\n" + prompt.encode("utf-8")[:64])
        return out_path


def _has_moviepy() -> bool:
    try:
        from moviepy.editor import ImageClip  # noqa: F401

        return True
    except Exception:
        return False


@pytest.mark.skipif(not _has_moviepy(), reason="moviepy not installed")
def test_end_to_end_video_pipeline(tmp_path, monkeypatch):
    # Create sample markdown
    md = tmp_path / "sample.md"
    md.write_text("# Chapter 1\n\nThis is one. This is two.", encoding="utf-8")

    # Configure dummy providers
    monkeypatch.setenv("TTS_PROVIDER", "dummy")
    monkeypatch.setenv("IMAGE_PROVIDER", "dummy")
    monkeypatch.setenv("STORAGE_PROVIDER", "dummy")
    monkeypatch.setenv("LLM_OUT_DIR", str(tmp_path / "out"))

    desc = build_graph_description(str(md))
    google = MockGoogleServices()
    result = run_graph_description(desc, google=google)

    composer = VideoComposer()
    # Monkeypatch compose_chapter to avoid requiring moviepy
    def stub_compose(self, slides, out_path, include_subtitles=True):
        with open(out_path, "wb") as f:
            f.write(b"MP4")
        srt_path = os.path.splitext(out_path)[0] + ".srt"
        with open(srt_path, "w", encoding="utf-8") as f:
            f.write("1\n00:00:00,000 --> 00:00:01,000\nHello\n")
        return out_path

    import agent.video_composer as vc
    monkeypatch.setattr(vc.VideoComposer, "compose_chapter", stub_compose)

    # Compose videos for all chapters
    for chap in result["script_gen"]:
        slides = chap.get("slides", [])
        res = composer.compose_and_upload_chapter_video(slides, "runx", chap.get("chapter_id"))
        assert "video_url" in res
        assert res["video_url"]