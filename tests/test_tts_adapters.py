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
    
    # factory should default to dummy if provider not set
    adapter = get_tts_adapter(None)
    assert isinstance(adapter, DummyTTSAdapter)

    # When provider=google, the adapter is instantiated but will fail when synthesize is called
    # if the Google SDK is missing. This tests that synthesize raises ImportError.
    adapter2 = get_tts_adapter("google")
    assert isinstance(adapter2, GoogleTTSAdapter)
    
    # Block google imports to verify synthesize fails gracefully
    import builtins
    original_import = builtins.__import__
    
    def mock_import(name, *args, **kwargs):
        if 'google.cloud' in name or name == 'google.cloud':
            raise ImportError(f"Mocked: {name} not available")
        return original_import(name, *args, **kwargs)
    
    monkeypatch.setattr(builtins, '__import__', mock_import)
    
    # Now synthesize should raise ImportError
    try:
        adapter2.synthesize("test")
        assert False, "Expected ImportError"
    except ImportError as e:
        assert "google-cloud-texttospeech" in str(e)
