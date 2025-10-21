from __future__ import annotations

import os
from abc import ABC, abstractmethod
from typing import Optional


class StorageAdapter(ABC):
    """Simple storage adapter interface used to persist artifacts.

    Implementations must provide upload_file which uploads a local file and
    returns a canonical URL string for the uploaded artifact.
    """

    @abstractmethod
    def upload_file(self, local_path: str, dest_path: Optional[str] = None) -> str:
        raise NotImplementedError()

    @abstractmethod
    def download_file(self, remote_url: str, dest_path: str) -> str:
        raise NotImplementedError()


def get_storage_adapter(name: Optional[str] = None, **kwargs) -> Optional[StorageAdapter]:
    """Factory helper to create a storage adapter by name.

    Supported names:
    - 'gcs': Google Cloud Storage
    - 'minio': MinIO (S3-compatible)
    - 'dummy': Local filesystem (testing)
    
    If name is None, reads from STORAGE_PROVIDER or LLM_STORAGE env var.
    Returns None if no provider configured or on import errors.
    """
    chosen = name or os.getenv("STORAGE_PROVIDER") or os.getenv("LLM_STORAGE")
    if not chosen:
        return None
    
    chosen = chosen.lower()
    
    if chosen == "gcs":
        try:
            from .gcs_adapter import GCSStorageAdapter
            return GCSStorageAdapter(**kwargs)
        except Exception:
            # Fall back to None if GCS not available
            return None
    
    if chosen in ("minio", "s3"):
        try:
            from .minio_adapter import MinIOStorageAdapter
            return MinIOStorageAdapter(**kwargs)
        except Exception:
            # Fall back to None if MinIO not available
            return None
    
    if chosen == "dummy":
        # Lazy import to avoid importing test helpers at module import time
        from .dummy_storage import DummyStorageAdapter
        base_dir = kwargs.get("base_dir") or os.getenv("LLM_STORAGE_DIR")
        return DummyStorageAdapter(base_dir=base_dir)
    
    return None
