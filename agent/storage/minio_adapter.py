from __future__ import annotations

import os
from typing import Optional

from . import StorageAdapter


class MinIOStorageAdapter(StorageAdapter):
    """MinIO (S3-compatible) storage adapter for self-hosted artifact storage.
    
    Uses minio Python SDK to upload and download files.
    Can also work with AWS S3 by setting appropriate endpoint and credentials.
    """

    def __init__(
        self,
        bucket_name: Optional[str] = None,
        endpoint: Optional[str] = None,
        access_key: Optional[str] = None,
        secret_key: Optional[str] = None,
        secure: bool = True,
    ):
        self.bucket_name = bucket_name or os.getenv("MINIO_BUCKET") or "video-agent-artifacts"
        self.endpoint = endpoint or os.getenv("MINIO_ENDPOINT") or "localhost:9000"
        self.access_key = access_key or os.getenv("MINIO_ACCESS_KEY")
        self.secret_key = secret_key or os.getenv("MINIO_SECRET_KEY")
        self.secure = secure if os.getenv("MINIO_SECURE") is None else os.getenv("MINIO_SECURE").lower() == "true"
        self._client = None

    def _get_client(self):
        """Lazy initialization of MinIO client."""
        if self._client is None:
            try:
                from minio import Minio
            except ImportError:
                raise ImportError(
                    "minio is required for MinIOStorageAdapter. "
                    "Install it with: pip install minio"
                )
            
            if not self.access_key or not self.secret_key:
                raise ValueError(
                    "MinIO requires access_key and secret_key. "
                    "Set MINIO_ACCESS_KEY and MINIO_SECRET_KEY environment variables."
                )
            
            self._client = Minio(
                self.endpoint,
                access_key=self.access_key,
                secret_key=self.secret_key,
                secure=self.secure,
            )
            
            # Ensure bucket exists
            try:
                if not self._client.bucket_exists(self.bucket_name):
                    self._client.make_bucket(self.bucket_name)
            except Exception as e:
                # Log warning but don't fail - bucket might exist but we don't have list permission
                import warnings
                warnings.warn(f"Could not verify bucket existence: {e}", RuntimeWarning)
        
        return self._client

    def upload_file(self, local_path: str, dest_path: Optional[str] = None) -> str:
        """Upload a local file to MinIO and return its URL.
        
        Args:
            local_path: Path to local file to upload
            dest_path: Destination path in bucket (if None, uses basename)
            
        Returns:
            minio:// URL to the uploaded file
        """
        if not os.path.exists(local_path):
            raise FileNotFoundError(f"Local file not found: {local_path}")
        
        dest = dest_path or os.path.basename(local_path)
        # Normalize path separators for object storage (always use /)
        dest = dest.replace("\\", "/")
        
        client = self._get_client()
        
        # Upload file
        client.fput_object(
            self.bucket_name,
            dest,
            local_path,
        )
        
        # Return minio:// URL (custom scheme for this adapter)
        return f"minio://{self.bucket_name}/{dest}"

    def download_file(self, remote_url: str, dest_path: str) -> str:
        """Download a file from MinIO to local path.
        
        Args:
            remote_url: MinIO URL (minio://bucket/path format)
            dest_path: Local destination path
            
        Returns:
            Local path to downloaded file
        """
        if not remote_url.startswith("minio://"):
            raise ValueError(f"Invalid MinIO URL (must start with minio://): {remote_url}")
        
        # Parse minio://bucket/path
        parts = remote_url[8:].split("/", 1)
        if len(parts) != 2:
            raise ValueError(f"Invalid MinIO URL format: {remote_url}")
        
        bucket_name, object_path = parts
        
        # Ensure destination directory exists
        os.makedirs(os.path.dirname(dest_path) or ".", exist_ok=True)
        
        client = self._get_client()
        
        # Download file
        client.fget_object(bucket_name, object_path, dest_path)
        
        return dest_path
