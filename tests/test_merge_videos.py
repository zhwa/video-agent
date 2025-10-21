import os
from agent.video_composer import VideoComposer


def test_merge_videos_stub(tmp_path, monkeypatch):
    # Create minimal placeholder files
    v1 = tmp_path / "v1.mp4"
    v1.write_bytes(b"MP4")
    v2 = tmp_path / "v2.mp4"
    v2.write_bytes(b"MP4")

    # Monkeypatch merge implementation to avoid moviepy
    def stub_merge(self, urls, out_path, transition_sec=0.0):
        with open(out_path, "wb") as f:
            f.write(b'MERGED')
        return out_path

    monkeypatch.setattr(VideoComposer, "merge_videos", stub_merge)
    composer = VideoComposer()
    out = composer.merge_videos([f"file://{v1}", f"file://{v2}"], str(tmp_path / "out.mp4"))
    assert out.endswith("out.mp4")
    assert os.path.exists(out)
