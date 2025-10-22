import os
import types
import sys
import tempfile
from pathlib import Path
from agent.google import get_tts_adapter, DummyTTSAdapter, GoogleTTSAdapter


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


def test_google_tts_with_cache(tmp_path, monkeypatch):
    """Test Google TTS adapter with caching enabled."""
    # Create fake google module
    google = types.ModuleType("google")
    cloud = types.ModuleType("google.cloud")
    texttospeech_module = types.ModuleType("google.cloud.texttospeech")
    
    fake_audio = b"fake audio data"
    
    class FakeResponse:
        def __init__(self):
            self.audio_content = fake_audio
    
    class FakeClient:
        def synthesize_speech(self, input, voice, audio_config):
            return FakeResponse()
    
    class FakeSynthesisInput:
        def __init__(self, text):
            self.text = text
    
    class FakeVoiceParams:
        def __init__(self, language_code, name):
            self.language_code = language_code
            self.name = name
    
    class FakeAudioConfig:
        def __init__(self, audio_encoding):
            self.audio_encoding = audio_encoding
    
    class FakeAudioEncoding:
        MP3 = "MP3"
    
    texttospeech_module.TextToSpeechClient = FakeClient
    texttospeech_module.SynthesisInput = FakeSynthesisInput
    texttospeech_module.VoiceSelectionParams = FakeVoiceParams
    texttospeech_module.AudioConfig = FakeAudioConfig
    texttospeech_module.AudioEncoding = FakeAudioEncoding
    
    cloud.texttospeech = texttospeech_module
    google.cloud = cloud
    
    sys.modules["google"] = google
    sys.modules["google.cloud"] = cloud
    sys.modules["google.cloud.texttospeech"] = texttospeech_module
    
    monkeypatch.setenv("CACHE_DIR", str(tmp_path / "cache"))
    
    try:
        from agent.google.tts import GoogleTTSAdapter
        
        adapter = GoogleTTSAdapter(cache_enabled=True)
        
        # First generation
        out1 = tmp_path / "out1.mp3"
        result1 = adapter.synthesize("Hello world", out_path=str(out1))
        assert Path(result1).exists()
        assert Path(result1).read_bytes() == fake_audio
        
        # Second generation with same text should use cache
        out2 = tmp_path / "out2.mp3"
        result2 = adapter.synthesize("Hello world", out_path=str(out2))
        assert Path(result2).exists()
        assert Path(result2).read_bytes() == fake_audio
        
    finally:
        del sys.modules["google.cloud.texttospeech"]
        del sys.modules["google.cloud"]
        del sys.modules["google"]
