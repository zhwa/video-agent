import sys
import types
from pathlib import Path


def test_elevenlabs_adapter_with_cache(tmp_path, monkeypatch):
    """Test ElevenLabs adapter with caching enabled."""
    # Create fake elevenlabs module
    elevenlabs_module = types.ModuleType("elevenlabs")
    
    generated_audio = b"fake audio content"
    
    def fake_generate(text, voice, model, api_key):
        return generated_audio
    
    def fake_save(audio, filename):
        Path(filename).parent.mkdir(parents=True, exist_ok=True)
        Path(filename).write_bytes(audio)
    
    elevenlabs_module.generate = fake_generate
    elevenlabs_module.save = fake_save
    
    sys.modules["elevenlabs"] = elevenlabs_module
    
    # Set required env vars
    monkeypatch.setenv("ELEVENLABS_API_KEY", "test-key")
    monkeypatch.setenv("CACHE_DIR", str(tmp_path / "cache"))
    
    try:
        from agent.adapters.elevenlabs_tts import ElevenLabsTTSAdapter
        
        adapter = ElevenLabsTTSAdapter()
        
        # First generation
        out1 = tmp_path / "out1.mp3"
        result1 = adapter.synthesize("Hello world", out_path=str(out1))
        assert Path(result1).exists()
        assert Path(result1).read_bytes() == generated_audio
        
        # Second generation with same text should use cache
        out2 = tmp_path / "out2.mp3"
        result2 = adapter.synthesize("Hello world", out_path=str(out2))
        assert Path(result2).exists()
        # Should have copied from cache
        assert Path(result2).read_bytes() == generated_audio
        
    finally:
        del sys.modules["elevenlabs"]


def test_elevenlabs_adapter_missing_api_key():
    """Test that ElevenLabs adapter requires API key."""
    import sys
    import types
    
    elevenlabs_module = types.ModuleType("elevenlabs")
    elevenlabs_module.generate = lambda **kwargs: b""
    elevenlabs_module.save = lambda audio, filename: None
    sys.modules["elevenlabs"] = elevenlabs_module
    
    try:
        from agent.adapters.elevenlabs_tts import ElevenLabsTTSAdapter
        
        adapter = ElevenLabsTTSAdapter()  # No API key
        
        try:
            adapter.synthesize("test")
            assert False, "Should raise ValueError"
        except ValueError as e:
            assert "API key" in str(e)
    finally:
        del sys.modules["elevenlabs"]


def test_elevenlabs_adapter_missing_sdk():
    """Test that ElevenLabs adapter raises ImportError when SDK is missing."""
    import builtins
    original_import = builtins.__import__
    
    def mock_import(name, *args, **kwargs):
        if name == "elevenlabs":
            raise ImportError("Mocked: elevenlabs not available")
        return original_import(name, *args, **kwargs)
    
    builtins.__import__ = mock_import
    
    try:
        from agent.adapters.elevenlabs_tts import ElevenLabsTTSAdapter
        
        adapter = ElevenLabsTTSAdapter(api_key="test")
        
        try:
            adapter.synthesize("test")
            assert False, "Should raise ImportError"
        except ImportError as e:
            assert "elevenlabs" in str(e)
    finally:
        builtins.__import__ = original_import


def test_elevenlabs_factory_integration(monkeypatch):
    """Test that factory can create ElevenLabs adapter."""
    import sys
    import types
    
    # Mock elevenlabs module
    elevenlabs_module = types.ModuleType("elevenlabs")
    elevenlabs_module.generate = lambda **kwargs: b""
    elevenlabs_module.save = lambda audio, filename: None
    sys.modules["elevenlabs"] = elevenlabs_module
    
    monkeypatch.setenv("ELEVENLABS_API_KEY", "test-key")
    
    try:
        from agent.adapters import get_tts_adapter
        from agent.adapters.elevenlabs_tts import ElevenLabsTTSAdapter
        
        adapter = get_tts_adapter("elevenlabs")
        assert isinstance(adapter, ElevenLabsTTSAdapter)
    finally:
        del sys.modules["elevenlabs"]


def test_elevenlabs_fallback_to_dummy(monkeypatch):
    """Test that factory falls back to dummy when ElevenLabs SDK is missing."""
    import builtins
    original_import = builtins.__import__
    
    def mock_import(name, *args, **kwargs):
        if name == "elevenlabs" or "elevenlabs" in name:
            raise ImportError("Mocked")
        return original_import(name, *args, **kwargs)
    
    builtins.__import__ = mock_import
    
    try:
        from agent.adapters import get_tts_adapter, DummyTTSAdapter
        
        monkeypatch.setenv("TTS_PROVIDER", "elevenlabs")
        adapter = get_tts_adapter()
        
        # Should fall back to dummy
        assert isinstance(adapter, DummyTTSAdapter)
    finally:
        builtins.__import__ = original_import
