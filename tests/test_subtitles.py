from agent.video_composer import _generate_subtitle_entries, _write_subtitles
import tempfile


def test_generate_entries_and_write_srt(tmp_path):
    slides = [
        {"estimated_duration_sec": 4, "bullets": ["First bullet.", "Second bullet."], "speaker_notes": ""},
        {"estimated_duration_sec": 3, "speaker_notes": "Some longer speaker notes here."},
    ]
    entries = _generate_subtitle_entries(slides, wrap_width=40)
    assert len(entries) == 3
    out = tmp_path / "out.mp4"
    out.write_text("")
    srt = _write_subtitles(entries, str(out), fmt="srt")
    assert srt.endswith(".srt")
    from pathlib import Path
    assert Path(srt).exists()


def test_write_vtt(tmp_path):
    slides = [{"estimated_duration_sec": 2, "speaker_notes": "Note"}]
    entries = _generate_subtitle_entries(slides)
    out = tmp_path / "out.mp4"
    out.write_text("")
    vtt = _write_subtitles(entries, str(out), fmt="vtt")
    assert vtt.endswith(".vtt")
    from pathlib import Path
    assert Path(vtt).exists()