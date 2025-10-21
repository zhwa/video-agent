import os
import types
import sys
import tempfile
from agent.adapters import get_tts_adapter, DummyTTSAdapter, GoogleTTSAdapter


def test_dummy_tts_writes_text(tmp_path):
    adapter = DummyTTSAdapter()
    out = str(tmp_path / "out" / "dummy.wav")
    res = adapter.synthesize("Hello world", out_path=out)
    assert res == out
    assert (tmp_path / "out" / "dummy.wav").exists()


def test_google_tts_falls_back_when_sdk_missing(monkeypatch):
    # Ensure import error occurs if google client missing; get_tts_adapter should return Dummy
    monkeypatch.delenv("TTS_PROVIDER", raising=False)
    # Simulate that google library isn't present
    if "google" in sys.modules:
        del sys.modules["google"]
    # factory should default to dummy if provider not set
    adapter = get_tts_adapter(None)
    assert isinstance(adapter, DummyTTSAdapter)

    # When provider=google but package missing, the factory should still return Dummy
    adapter2 = get_tts_adapter("google")
    assert isinstance(adapter2, DummyTTSAdapter)
