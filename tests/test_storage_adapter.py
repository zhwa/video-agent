import os
import tempfile
import sys
import types
from agent.storage.dummy_storage import DummyStorageAdapter
from agent.storage import get_storage_adapter


def test_dummy_storage_upload_download(tmp_path):
    adapter = DummyStorageAdapter(base_dir=str(tmp_path / "store"))
    # create a temp file
    src = tmp_path / "hello.txt"
    src.write_text("hello world", encoding="utf-8")
    url = adapter.upload_file(str(src), dest_path="folder/hello.txt")
    assert url.startswith("file://")
    dest = tmp_path / "download.txt"
    downloaded = adapter.download_file(url, str(dest))
    assert os.path.exists(downloaded)
    assert open(downloaded, "r", encoding="utf-8").read() == "hello world"


def test_storage_factory_dummy(monkeypatch):
    """Test factory returns DummyStorageAdapter for dummy provider."""
    monkeypatch.setenv("STORAGE_PROVIDER", "dummy")
    adapter = get_storage_adapter()
    assert isinstance(adapter, DummyStorageAdapter)


def test_storage_factory_gcs_fallback(monkeypatch, tmp_path):
    """Test factory works with GCS even when SDK is not installed (lazy loading)."""
    # GCS adapter is instantiated lazily, so it won't fail until _get_client is called
    monkeypatch.setenv("STORAGE_PROVIDER", "gcs")
    
    adapter = get_storage_adapter()
    # Adapter should be created (lazy initialization)
    from agent.storage.gcs_adapter import GCSStorageAdapter
    assert isinstance(adapter, GCSStorageAdapter)
    
    # But using it without SDK should fail
    import builtins
    original_import = builtins.__import__
    
    def mock_import(name, *args, **kwargs):
        if "google.cloud.storage" in name:
            raise ImportError("Mocked")
        return original_import(name, *args, **kwargs)
    
    monkeypatch.setattr(builtins, "__import__", mock_import)
    
    test_file = tmp_path / "test.txt"
    test_file.write_text("test")
    
    try:
        adapter.upload_file(str(test_file))
        assert False, "Should raise ImportError"
    except ImportError:
        pass  # Expected


def test_storage_factory_minio_fallback(monkeypatch, tmp_path):
    """Test factory works with MinIO even when SDK is not installed (lazy loading)."""
    # MinIO adapter is instantiated lazily, so it won't fail until _get_client is called
    monkeypatch.setenv("STORAGE_PROVIDER", "minio")
    monkeypatch.setenv("MINIO_ACCESS_KEY", "test")
    monkeypatch.setenv("MINIO_SECRET_KEY", "test")
    
    adapter = get_storage_adapter()
    # Adapter should be created (lazy initialization)
    from agent.storage.minio_adapter import MinIOStorageAdapter
    assert isinstance(adapter, MinIOStorageAdapter)
    
    # But using it without SDK should fail
    import builtins
    original_import = builtins.__import__
    
    def mock_import(name, *args, **kwargs):
        if name == "minio":
            raise ImportError("Mocked")
        return original_import(name, *args, **kwargs)
    
    monkeypatch.setattr(builtins, "__import__", mock_import)
    
    test_file = tmp_path / "test.txt"
    test_file.write_text("test")
    
    try:
        adapter.upload_file(str(test_file))
        assert False, "Should raise ImportError"
    except ImportError:
        pass  # Expected


def test_storage_factory_no_provider():
    """Test factory returns None when no provider configured."""
    adapter = get_storage_adapter()
    # Should return None when no provider set
    assert adapter is None
