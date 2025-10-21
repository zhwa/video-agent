import os
import sys
import types
from pathlib import Path


def test_minio_adapter_upload_download(tmp_path, monkeypatch):
    """Test MinIO adapter with mocked minio SDK."""
    
    # Create a fake minio module
    minio_module = types.ModuleType("minio")
    
    # Track uploaded files
    uploaded_files = {}
    
    class FakeMinio:
        def __init__(self, endpoint, access_key, secret_key, secure=True):
            self.endpoint = endpoint
            self.access_key = access_key
            self.secret_key = secret_key
            self.secure = secure
        
        def bucket_exists(self, bucket_name):
            return True
        
        def make_bucket(self, bucket_name):
            pass
        
        def fput_object(self, bucket_name, object_name, file_path):
            # Read file and store in fake storage
            with open(file_path, "rb") as f:
                key = f"{bucket_name}/{object_name}"
                uploaded_files[key] = f.read()
        
        def fget_object(self, bucket_name, object_name, file_path):
            # Write stored content to file
            os.makedirs(os.path.dirname(file_path) or ".", exist_ok=True)
            key = f"{bucket_name}/{object_name}"
            with open(file_path, "wb") as f:
                f.write(uploaded_files.get(key, b""))
    
    minio_module.Minio = FakeMinio
    sys.modules["minio"] = minio_module
    
    # Set required env vars
    monkeypatch.setenv("MINIO_ACCESS_KEY", "test-access")
    monkeypatch.setenv("MINIO_SECRET_KEY", "test-secret")
    
    try:
        from agent.storage.minio_adapter import MinIOStorageAdapter
        
        adapter = MinIOStorageAdapter(bucket_name="test-bucket", endpoint="localhost:9000")
        
        # Create a test file
        test_file = tmp_path / "test.txt"
        test_file.write_text("Hello MinIO!", encoding="utf-8")
        
        # Upload
        url = adapter.upload_file(str(test_file), dest_path="uploads/test.txt")
        assert url == "minio://test-bucket/uploads/test.txt"
        assert "test-bucket/uploads/test.txt" in uploaded_files
        assert uploaded_files["test-bucket/uploads/test.txt"] == b"Hello MinIO!"
        
        # Download
        dest = tmp_path / "downloaded.txt"
        result = adapter.download_file(url, str(dest))
        assert result == str(dest)
        assert dest.read_text(encoding="utf-8") == "Hello MinIO!"
    finally:
        del sys.modules["minio"]


def test_minio_adapter_missing_sdk(tmp_path):
    """Test that MinIO adapter raises ImportError when SDK is missing."""
    import builtins
    original_import = builtins.__import__
    
    def mock_import(name, *args, **kwargs):
        if name == "minio":
            raise ImportError("Mocked: minio not available")
        return original_import(name, *args, **kwargs)
    
    builtins.__import__ = mock_import
    
    try:
        from agent.storage.minio_adapter import MinIOStorageAdapter
        adapter = MinIOStorageAdapter(access_key="test", secret_key="test")
        
        # Create a temp file
        test_file = tmp_path / "test.txt"
        test_file.write_text("test")
        
        # Should raise ImportError when trying to use the adapter
        try:
            adapter.upload_file(str(test_file))
            assert False, "Expected ImportError"
        except ImportError as e:
            assert "minio" in str(e)
    finally:
        builtins.__import__ = original_import


def test_minio_adapter_missing_credentials():
    """Test that MinIO adapter requires credentials."""
    import sys
    import types
    
    minio_module = types.ModuleType("minio")
    
    class FakeMinio:
        def __init__(self, endpoint, access_key, secret_key, secure=True):
            pass
    
    minio_module.Minio = FakeMinio
    sys.modules["minio"] = minio_module
    
    try:
        from agent.storage.minio_adapter import MinIOStorageAdapter
        
        # Create adapter without credentials
        adapter = MinIOStorageAdapter()
        
        # Should raise ValueError when trying to get client
        try:
            adapter._get_client()
            assert False, "Expected ValueError for missing credentials"
        except ValueError as e:
            assert "access_key" in str(e) or "secret_key" in str(e)
    finally:
        del sys.modules["minio"]


def test_minio_adapter_invalid_url():
    """Test MinIO adapter with invalid URL formats."""
    import sys
    import types
    
    minio_module = types.ModuleType("minio")
    
    class FakeMinio:
        def __init__(self, endpoint, access_key, secret_key, secure=True):
            pass
        def bucket_exists(self, bucket_name):
            return True
    
    minio_module.Minio = FakeMinio
    sys.modules["minio"] = minio_module
    
    try:
        from agent.storage.minio_adapter import MinIOStorageAdapter
        
        adapter = MinIOStorageAdapter(access_key="test", secret_key="test")
        
        # Test invalid URL schemes
        try:
            adapter.download_file("http://example.com/file.txt", "/tmp/out.txt")
            assert False, "Should raise ValueError for non-minio:// URL"
        except ValueError as e:
            assert "minio://" in str(e)
        
        # Test malformed minio:// URL
        try:
            adapter.download_file("minio://bucket-only", "/tmp/out.txt")
            assert False, "Should raise ValueError for malformed URL"
        except ValueError as e:
            assert "Invalid MinIO URL" in str(e)
    finally:
        del sys.modules["minio"]


def test_minio_adapter_windows_paths(tmp_path, monkeypatch):
    """Test that MinIO adapter normalizes Windows paths correctly."""
    import sys
    import types
    
    uploaded_paths = []
    
    minio_module = types.ModuleType("minio")
    
    class FakeMinio:
        def __init__(self, endpoint, access_key, secret_key, secure=True):
            pass
        
        def bucket_exists(self, bucket_name):
            return True
        
        def fput_object(self, bucket_name, object_name, file_path):
            uploaded_paths.append(object_name)
    
    minio_module.Minio = FakeMinio
    sys.modules["minio"] = minio_module
    
    monkeypatch.setenv("MINIO_ACCESS_KEY", "test")
    monkeypatch.setenv("MINIO_SECRET_KEY", "test")
    
    try:
        from agent.storage.minio_adapter import MinIOStorageAdapter
        
        adapter = MinIOStorageAdapter()
        
        test_file = tmp_path / "test.txt"
        test_file.write_text("test")
        
        # Upload with Windows-style path
        adapter.upload_file(str(test_file), dest_path="folder\\subfolder\\file.txt")
        
        # Should be normalized to forward slashes
        assert uploaded_paths[-1] == "folder/subfolder/file.txt"
    finally:
        del sys.modules["minio"]
