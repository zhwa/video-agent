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

    Supported names: 'dummy' (local filesystem copy). If name is None or unknown
    returns None.
    """
    chosen = name or os.getenv("LLM_STORAGE")
    if not chosen:
        return None
    chosen = chosen.lower()
    if chosen == "dummy":
        # Lazy import to avoid importing test helpers at module import time
        from .dummy_storage import DummyStorageAdapter

        base_dir = kwargs.get("base_dir") or os.getenv("LLM_STORAGE_DIR")
        return DummyStorageAdapter(base_dir=base_dir)
    return None
