"""Shared pytest fixtures for all tests."""

import shutil
import os
import pytest


@pytest.fixture
def dummy_storage(tmp_path):
    """Simple local file storage adapter for testing.
    
    Replaces DummyStorageAdapter from agent.google.storage.
    Provides upload_file() and download_file() methods for test isolation.
    """
    storage_dir = tmp_path / "storage"
    storage_dir.mkdir(parents=True, exist_ok=True)
    
    class DummyStorage:
        def __init__(self, base_dir):
            self.base_dir = base_dir
            os.makedirs(self.base_dir, exist_ok=True)
        
        def upload_file(self, local_path: str, dest_path: str = None) -> str:
            """Copy file to storage and return file:// URL."""
            dest = dest_path or os.path.basename(local_path)
            full = os.path.join(self.base_dir, dest)
            # Create parent directories if they don't exist
            os.makedirs(os.path.dirname(full), exist_ok=True)
            shutil.copy(local_path, full)
            return f"file://{os.path.abspath(full)}"
        
        def download_file(self, remote_url: str, dest_path: str) -> str:
            """Copy file from storage (only supports file:// URLs)."""
            if remote_url.startswith("file://"):
                src = remote_url[len("file://"):]
                shutil.copy(src, dest_path)
                return dest_path
            raise NotImplementedError("DummyStorage only supports file:// URLs")
    
    return DummyStorage(str(storage_dir))
