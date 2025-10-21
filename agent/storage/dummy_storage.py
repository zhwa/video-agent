from __future__ import annotations

import os
import shutil
from typing import Optional

from . import StorageAdapter


class DummyStorageAdapter(StorageAdapter):
    def __init__(self, base_dir: Optional[str] = None):
        self.base_dir = base_dir or "workspace/storage"
        os.makedirs(self.base_dir, exist_ok=True)

    def upload_file(self, local_path: str, dest_path: Optional[str] = None) -> str:
        # Copy the file into base_dir and return file:// URL
        dest = dest_path or os.path.basename(local_path)
        full = os.path.join(self.base_dir, dest)
        # Create parent directories if they don't exist
        os.makedirs(os.path.dirname(full), exist_ok=True)
        shutil.copy(local_path, full)
        return f"file://{os.path.abspath(full)}"

    def download_file(self, remote_url: str, dest_path: str) -> str:
        # Only supports file:// urls for dummy adapter
        if remote_url.startswith("file://"):
            src = remote_url[len("file://") :]
            shutil.copy(src, dest_path)
            return dest_path
        raise NotImplementedError("DummyStorageAdapter only supports file:// URLs")
