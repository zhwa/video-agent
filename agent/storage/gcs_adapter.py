from __future__ import annotations

import os
from typing import Optional

from . import StorageAdapter


class GCSStorageAdapter(StorageAdapter):
    """Google Cloud Storage adapter for artifact persistence.
    
    Uses google-cloud-storage SDK to upload and download files.
    Credentials are read from GOOGLE_APPLICATION_CREDENTIALS env var.
    """

    def __init__(
        self,
        bucket_name: Optional[str] = None,
        project: Optional[str] = None,
        credentials_path: Optional[str] = None,
    ):
        self.bucket_name = bucket_name or os.getenv("GCS_BUCKET") or "video-agent-artifacts"
        self.project = project or os.getenv("GCP_PROJECT")
        self.credentials_path = credentials_path or os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
        self._client = None
        self._bucket = None

    def _get_client(self):
        """Lazy initialization of GCS client."""
        if self._client is None:
            try:
                from google.cloud import storage
            except ImportError:
                raise ImportError(
                    "google-cloud-storage is required for GCSStorageAdapter. "
                    "Install it with: pip install google-cloud-storage"
                )
            
            # Initialize client with credentials if provided
            if self.credentials_path:
                self._client = storage.Client.from_service_account_json(
                    self.credentials_path, project=self.project
                )
            else:
                # Use Application Default Credentials
                self._client = storage.Client(project=self.project)
            
            self._bucket = self._client.bucket(self.bucket_name)
        
        return self._client

    def upload_file(self, local_path: str, dest_path: Optional[str] = None) -> str:
        """Upload a local file to GCS and return its public URL.
        
        Args:
            local_path: Path to local file to upload
            dest_path: Destination path in bucket (if None, uses basename)
            
        Returns:
            gs:// URL to the uploaded file
        """
        if not os.path.exists(local_path):
            raise FileNotFoundError(f"Local file not found: {local_path}")
        
        dest = dest_path or os.path.basename(local_path)
        # Normalize path separators for GCS (always use /)
        dest = dest.replace("\\", "/")
        
        client = self._get_client()
        blob = self._bucket.blob(dest)
        
        # Upload file
        blob.upload_from_filename(local_path)
        
        # Return gs:// URL
        return f"gs://{self.bucket_name}/{dest}"

    def download_file(self, remote_url: str, dest_path: str) -> str:
        """Download a file from GCS to local path.
        
        Args:
            remote_url: GCS URL (gs://bucket/path format)
            dest_path: Local destination path
            
        Returns:
            Local path to downloaded file
        """
        if not remote_url.startswith("gs://"):
            raise ValueError(f"Invalid GCS URL (must start with gs://): {remote_url}")
        
        # Parse gs://bucket/path
        parts = remote_url[5:].split("/", 1)
        if len(parts) != 2:
            raise ValueError(f"Invalid GCS URL format: {remote_url}")
        
        bucket_name, blob_path = parts
        
        # Ensure destination directory exists
        os.makedirs(os.path.dirname(dest_path) or ".", exist_ok=True)
        
        client = self._get_client()
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(blob_path)
        
        # Download file
        blob.download_to_filename(dest_path)
        
        return dest_path
