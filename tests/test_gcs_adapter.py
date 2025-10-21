import os
import sys
import types
from pathlib import Path


def test_gcs_adapter_upload_download(tmp_path, monkeypatch):
    """Test GCS adapter with mocked google-cloud-storage SDK."""
    
    # Create a fake google.cloud.storage module
    google = types.ModuleType("google")
    cloud = types.ModuleType("google.cloud")
    storage_module = types.ModuleType("google.cloud.storage")
    
    # Track uploaded files
    uploaded_files = {}
    
    class FakeBlob:
        def __init__(self, name):
            self.name = name
        
        def upload_from_filename(self, filename):
            # Read file content and store in our fake storage
            with open(filename, "rb") as f:
                uploaded_files[self.name] = f.read()
        
        def download_to_filename(self, filename):
            # Write stored content to file
            os.makedirs(os.path.dirname(filename) or ".", exist_ok=True)
            with open(filename, "wb") as f:
                f.write(uploaded_files.get(self.name, b""))
    
    class FakeBucket:
        def __init__(self, name):
            self.name = name
        
        def blob(self, name):
            return FakeBlob(name)
    
    class FakeClient:
        @classmethod
        def from_service_account_json(cls, path, project=None):
            return cls()
        
        def __init__(self, project=None):
            self.project = project
        
        def bucket(self, name):
            return FakeBucket(name)
    
    storage_module.Client = FakeClient
    cloud.storage = storage_module
    google.cloud = cloud
    
    sys.modules["google"] = google
    sys.modules["google.cloud"] = cloud
    sys.modules["google.cloud.storage"] = storage_module
    
    # Now test the adapter
    from agent.storage.gcs_adapter import GCSStorageAdapter
    
    adapter = GCSStorageAdapter(bucket_name="test-bucket")
    
    # Create a test file
    test_file = tmp_path / "test.txt"
    test_file.write_text("Hello GCS!", encoding="utf-8")
    
    # Upload
    url = adapter.upload_file(str(test_file), dest_path="uploads/test.txt")
    assert url == "gs://test-bucket/uploads/test.txt"
    assert "uploads/test.txt" in uploaded_files
    assert uploaded_files["uploads/test.txt"] == b"Hello GCS!"
    
    # Download
    dest = tmp_path / "downloaded.txt"
    result = adapter.download_file(url, str(dest))
    assert result == str(dest)
    assert dest.read_text(encoding="utf-8") == "Hello GCS!"
    
    # Cleanup
    del sys.modules["google.cloud.storage"]
    del sys.modules["google.cloud"]
    del sys.modules["google"]


def test_gcs_adapter_missing_sdk(tmp_path):
    """Test that GCS adapter raises ImportError when SDK is missing."""
    import builtins
    original_import = builtins.__import__
    
    def mock_import(name, *args, **kwargs):
        if "google.cloud.storage" in name or name == "google.cloud.storage":
            raise ImportError("Mocked: google-cloud-storage not available")
        return original_import(name, *args, **kwargs)
    
    # Temporarily replace __import__
    builtins.__import__ = mock_import
    
    try:
        from agent.storage.gcs_adapter import GCSStorageAdapter
        adapter = GCSStorageAdapter()
        
        # Create a temp file
        test_file = tmp_path / "test.txt"
        test_file.write_text("test")
        
        # Should raise ImportError when trying to use the adapter
        try:
            adapter.upload_file(str(test_file))
            assert False, "Expected ImportError"
        except ImportError as e:
            assert "google-cloud-storage" in str(e)
    finally:
        builtins.__import__ = original_import


def test_gcs_adapter_invalid_url():
    """Test GCS adapter with invalid URL formats."""
    import sys
    import types
    
    # Create minimal fake module
    google = types.ModuleType("google")
    cloud = types.ModuleType("google.cloud")
    storage_module = types.ModuleType("google.cloud.storage")
    
    class FakeClient:
        def __init__(self, project=None):
            pass
        def bucket(self, name):
            return None
    
    storage_module.Client = FakeClient
    cloud.storage = storage_module
    google.cloud = cloud
    
    sys.modules["google"] = google
    sys.modules["google.cloud"] = cloud
    sys.modules["google.cloud.storage"] = storage_module
    
    try:
        from agent.storage.gcs_adapter import GCSStorageAdapter
        adapter = GCSStorageAdapter()
        
        # Test invalid URL schemes
        try:
            adapter.download_file("http://example.com/file.txt", "/tmp/out.txt")
            assert False, "Should raise ValueError for non-gs:// URL"
        except ValueError as e:
            assert "gs://" in str(e)
        
        # Test malformed gs:// URL
        try:
            adapter.download_file("gs://bucket-only", "/tmp/out.txt")
            assert False, "Should raise ValueError for malformed URL"
        except ValueError as e:
            assert "Invalid GCS URL" in str(e)
    finally:
        del sys.modules["google.cloud.storage"]
        del sys.modules["google.cloud"]
        del sys.modules["google"]


def test_gcs_adapter_windows_paths(tmp_path, monkeypatch):
    """Test that GCS adapter normalizes Windows paths correctly."""
    import sys
    import types
    
    uploaded_paths = []
    
    # Create fake module
    google = types.ModuleType("google")
    cloud = types.ModuleType("google.cloud")
    storage_module = types.ModuleType("google.cloud.storage")
    
    class FakeBlob:
        def __init__(self, name):
            uploaded_paths.append(name)
            self.name = name
        
        def upload_from_filename(self, filename):
            pass
    
    class FakeBucket:
        def blob(self, name):
            return FakeBlob(name)
    
    class FakeClient:
        def __init__(self, project=None):
            pass
        def bucket(self, name):
            return FakeBucket()
    
    storage_module.Client = FakeClient
    cloud.storage = storage_module
    google.cloud = cloud
    
    sys.modules["google"] = google
    sys.modules["google.cloud"] = cloud
    sys.modules["google.cloud.storage"] = storage_module
    
    try:
        from agent.storage.gcs_adapter import GCSStorageAdapter
        adapter = GCSStorageAdapter()
        
        test_file = tmp_path / "test.txt"
        test_file.write_text("test")
        
        # Upload with Windows-style path
        adapter.upload_file(str(test_file), dest_path="folder\\subfolder\\file.txt")
        
        # Should be normalized to forward slashes
        assert uploaded_paths[-1] == "folder/subfolder/file.txt"
    finally:
        del sys.modules["google.cloud.storage"]
        del sys.modules["google.cloud"]
        del sys.modules["google"]
