"""Simple local file storage for Google-only video agent.

For production use with Google Cloud Storage, use gsutil or Cloud Storage libraries directly.
This module provides a minimal local file storage for development and testing.
"""
from __future__ import annotations
import os
import shutil
from pathlib import Path
from typing import Optional

class DummyStorageAdapter:
    """Local filesystem storage adapter for development and testing.

    Returns file:// URLs for local files. Does not upload to cloud storage.
    """

    def upload_file(self, local_path: str, dest_path: Optional[str] = None) -> str:
        """Return a file:// URL for the local file (no actual upload).

        Args:
            local_path: Path to local file
            dest_path: Ignored (local storage only)

        Returns:
            file:// URL pointing to the local file
        """
        # Normalize path and return as file:// URL
        abs_path = Path(local_path).resolve()
        return abs_path.as_uri()

    def download_file(self, remote_url: str, dest_path: str) -> str:
        """Copy local file to destination (no actual download).

        Args:
            remote_url: file:// URL or local path
            dest_path: Destination path

        Returns:
            Destination path
        """
        # Handle file:// URLs
        if remote_url.startswith("file://"):
            # Remove file:// prefix and any leading slashes on Windows
            source_path = remote_url[7:]
            if os.name == "nt" and source_path.startswith("/"):
                source_path = source_path[1:]
        else:
            source_path = remote_url

        # Ensure destination directory exists
        os.makedirs(os.path.dirname(dest_path) or ".", exist_ok=True)

        # Copy file
        shutil.copy2(source_path, dest_path)
        return dest_path

def get_storage_adapter() -> DummyStorageAdapter:
    """Get storage adapter (always returns DummyStorageAdapter for local development).

    For production Google Cloud Storage usage, integrate with Cloud Storage SDK directly
    instead of using this adapter pattern.
    """
    return DummyStorageAdapter()