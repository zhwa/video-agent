import sys
import types
from pathlib import Path


def test_dummy_image_adapter(tmp_path):
    """Test that dummy image adapter creates a file."""
    from agent.adapters.image import DummyImageAdapter
    
    adapter = DummyImageAdapter()
    out_path = tmp_path / "test.png"
    
    result = adapter.generate_image("a beautiful sunset", out_path=str(out_path))
    assert result == str(out_path)
    assert out_path.exists()
    
    # Check it has PNG header
    content = out_path.read_bytes()
    assert content.startswith(b"\x89PNG\r\n\x1a\n")
    assert b"beautiful sunset" in content


def test_stability_adapter_with_cache(tmp_path, monkeypatch):
    """Test Stability adapter with caching enabled."""
    # Create fake stability modules
    stability_sdk = types.ModuleType("stability_sdk")
    client_module = types.ModuleType("stability_sdk.client")
    interfaces = types.ModuleType("stability_sdk.interfaces")
    gooseai = types.ModuleType("stability_sdk.interfaces.gooseai")
    generation_module = types.ModuleType("stability_sdk.interfaces.gooseai.generation")
    generation_pb2 = types.ModuleType("stability_sdk.interfaces.gooseai.generation.generation_pb2")
    
    fake_image_data = b"\x89PNG\r\n\x1a\nfake image data"
    
    # Mock artifact type
    generation_pb2.ARTIFACT_IMAGE = 1
    
    class FakeArtifact:
        def __init__(self):
            self.type = 1  # ARTIFACT_IMAGE
            self.binary = fake_image_data
    
    class FakeResponse:
        def __init__(self):
            self.artifacts = [FakeArtifact()]
    
    class FakeStabilityInference:
        def __init__(self, key, engine):
            self.key = key
            self.engine = engine
        
        def generate(self, **kwargs):
            return [FakeResponse()]
    
    client_module.StabilityInference = FakeStabilityInference
    
    # Build module hierarchy
    generation_pb2.ARTIFACT_IMAGE = 1
    generation_module.generation_pb2 = generation_pb2
    gooseai.generation = generation_module
    interfaces.gooseai = gooseai
    stability_sdk.interfaces = interfaces
    stability_sdk.client = client_module
    
    sys.modules["stability_sdk"] = stability_sdk
    sys.modules["stability_sdk.client"] = client_module
    sys.modules["stability_sdk.interfaces"] = interfaces
    sys.modules["stability_sdk.interfaces.gooseai"] = gooseai
    sys.modules["stability_sdk.interfaces.gooseai.generation"] = generation_module
    sys.modules["stability_sdk.interfaces.gooseai.generation.generation_pb2"] = generation_pb2
    
    monkeypatch.setenv("STABILITY_API_KEY", "test-key")
    monkeypatch.setenv("CACHE_DIR", str(tmp_path / "cache"))
    
    try:
        from agent.adapters.stability_adapter import StabilityImageAdapter
        
        adapter = StabilityImageAdapter()
        
        # First generation
        out1 = tmp_path / "out1.png"
        result1 = adapter.generate_image("a cat", out_path=str(out1))
        assert Path(result1).exists()
        assert Path(result1).read_bytes() == fake_image_data
        
        # Second generation with same prompt should use cache
        out2 = tmp_path / "out2.png"
        result2 = adapter.generate_image("a cat", out_path=str(out2))
        assert Path(result2).exists()
        assert Path(result2).read_bytes() == fake_image_data
        
    finally:
        # Cleanup
        for mod in list(sys.modules.keys()):
            if mod.startswith("stability_sdk"):
                del sys.modules[mod]


def test_stability_adapter_missing_api_key():
    """Test that Stability adapter requires API key."""
    import sys
    import types
    
    # Create minimal fake modules
    stability_sdk = types.ModuleType("stability_sdk")
    client_module = types.ModuleType("stability_sdk.client")
    interfaces = types.ModuleType("stability_sdk.interfaces")
    gooseai = types.ModuleType("stability_sdk.interfaces.gooseai")
    generation_module = types.ModuleType("stability_sdk.interfaces.gooseai.generation")
    generation_pb2 = types.ModuleType("stability_sdk.interfaces.gooseai.generation.generation_pb2")
    
    generation_pb2.ARTIFACT_IMAGE = 1
    generation_module.generation_pb2 = generation_pb2
    gooseai.generation = generation_module
    interfaces.gooseai = gooseai
    stability_sdk.interfaces = interfaces
    stability_sdk.client = client_module
    
    sys.modules["stability_sdk"] = stability_sdk
    sys.modules["stability_sdk.client"] = client_module
    sys.modules["stability_sdk.interfaces"] = interfaces
    sys.modules["stability_sdk.interfaces.gooseai"] = gooseai
    sys.modules["stability_sdk.interfaces.gooseai.generation"] = generation_module
    sys.modules["stability_sdk.interfaces.gooseai.generation.generation_pb2"] = generation_pb2
    
    try:
        from agent.adapters.stability_adapter import StabilityImageAdapter
        
        adapter = StabilityImageAdapter()  # No API key
        
        try:
            adapter.generate_image("test")
            assert False, "Should raise ValueError"
        except ValueError as e:
            assert "API key" in str(e)
    finally:
        for mod in list(sys.modules.keys()):
            if mod.startswith("stability_sdk"):
                del sys.modules[mod]


def test_replicate_adapter_with_cache(tmp_path, monkeypatch):
    """Test Replicate adapter with caching enabled."""
    # Create fake replicate module
    replicate_module = types.ModuleType("replicate")
    
    fake_image_data = b"\x89PNG\r\n\x1a\nfake replicate image"
    fake_url = "https://example.com/image.png"
    
    def fake_run(model, input):
        # Return a URL (typical Replicate behavior)
        return [fake_url]
    
    replicate_module.run = fake_run
    
    sys.modules["replicate"] = replicate_module
    
    # Mock urllib to intercept download
    import urllib.request
    original_urlretrieve = urllib.request.urlretrieve
    
    def fake_urlretrieve(url, filename):
        assert url == fake_url
        Path(filename).write_bytes(fake_image_data)
    
    urllib.request.urlretrieve = fake_urlretrieve
    
    monkeypatch.setenv("REPLICATE_API_TOKEN", "test-token")
    monkeypatch.setenv("CACHE_DIR", str(tmp_path / "cache"))
    
    try:
        from agent.adapters.replicate_adapter import ReplicateImageAdapter
        
        adapter = ReplicateImageAdapter()
        
        # First generation
        out1 = tmp_path / "out1.png"
        result1 = adapter.generate_image("a dog", out_path=str(out1))
        assert Path(result1).exists()
        assert Path(result1).read_bytes() == fake_image_data
        
        # Second generation with same prompt should use cache
        out2 = tmp_path / "out2.png"
        result2 = adapter.generate_image("a dog", out_path=str(out2))
        assert Path(result2).exists()
        assert Path(result2).read_bytes() == fake_image_data
        
    finally:
        urllib.request.urlretrieve = original_urlretrieve
        del sys.modules["replicate"]


def test_replicate_adapter_missing_api_token():
    """Test that Replicate adapter requires API token."""
    import sys
    import types
    
    replicate_module = types.ModuleType("replicate")
    replicate_module.run = lambda model, input: ["url"]
    sys.modules["replicate"] = replicate_module
    
    try:
        from agent.adapters.replicate_adapter import ReplicateImageAdapter
        
        adapter = ReplicateImageAdapter()  # No API token
        
        try:
            adapter.generate_image("test")
            assert False, "Should raise ValueError"
        except ValueError as e:
            assert "API token" in str(e)
    finally:
        del sys.modules["replicate"]


def test_image_adapter_factory_stability(monkeypatch):
    """Test that factory can create Stability adapter."""
    import sys
    import types
    
    # Mock stability modules
    stability_sdk = types.ModuleType("stability_sdk")
    client_module = types.ModuleType("stability_sdk.client")
    interfaces = types.ModuleType("stability_sdk.interfaces")
    gooseai = types.ModuleType("stability_sdk.interfaces.gooseai")
    generation_module = types.ModuleType("stability_sdk.interfaces.gooseai.generation")
    generation_pb2 = types.ModuleType("stability_sdk.interfaces.gooseai.generation.generation_pb2")
    
    generation_pb2.ARTIFACT_IMAGE = 1
    generation_module.generation_pb2 = generation_pb2
    gooseai.generation = generation_module
    interfaces.gooseai = gooseai
    stability_sdk.interfaces = interfaces
    stability_sdk.client = client_module
    
    sys.modules["stability_sdk"] = stability_sdk
    sys.modules["stability_sdk.client"] = client_module
    sys.modules["stability_sdk.interfaces"] = interfaces
    sys.modules["stability_sdk.interfaces.gooseai"] = gooseai
    sys.modules["stability_sdk.interfaces.gooseai.generation"] = generation_module
    sys.modules["stability_sdk.interfaces.gooseai.generation.generation_pb2"] = generation_pb2
    
    monkeypatch.setenv("STABILITY_API_KEY", "test-key")
    
    try:
        from agent.adapters import get_image_adapter
        from agent.adapters.stability_adapter import StabilityImageAdapter
        
        adapter = get_image_adapter("stability")
        assert isinstance(adapter, StabilityImageAdapter)
    finally:
        for mod in list(sys.modules.keys()):
            if mod.startswith("stability_sdk"):
                del sys.modules[mod]


def test_image_adapter_factory_replicate(monkeypatch):
    """Test that factory can create Replicate adapter."""
    import sys
    import types
    
    replicate_module = types.ModuleType("replicate")
    replicate_module.run = lambda model, input: ["url"]
    sys.modules["replicate"] = replicate_module
    
    monkeypatch.setenv("REPLICATE_API_TOKEN", "test-token")
    
    try:
        from agent.adapters import get_image_adapter
        from agent.adapters.replicate_adapter import ReplicateImageAdapter
        
        adapter = get_image_adapter("replicate")
        assert isinstance(adapter, ReplicateImageAdapter)
    finally:
        del sys.modules["replicate"]


def test_image_adapter_factory_dummy():
    """Test that factory defaults to dummy adapter."""
    from agent.adapters import get_image_adapter
    from agent.adapters.image import DummyImageAdapter
    
    adapter = get_image_adapter()
    assert isinstance(adapter, DummyImageAdapter)


def test_image_adapter_fallback_to_dummy(monkeypatch):
    """Test that factory uses dummy adapter when no provider is set."""
    from agent.adapters import get_image_adapter
    from agent.adapters.image import DummyImageAdapter
    
    # No IMAGE_PROVIDER set - should default to dummy
    adapter = get_image_adapter()
    assert isinstance(adapter, DummyImageAdapter)
    
    # Explicitly request dummy
    adapter2 = get_image_adapter("dummy")
    assert isinstance(adapter2, DummyImageAdapter)
