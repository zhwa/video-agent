from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Dict, Optional


def compute_cache_key(data: Any) -> str:
    """Compute a stable hash key for arbitrary data.
    
    Args:
        data: Any JSON-serializable data (string, dict, etc.)
        
    Returns:
        SHA256 hex digest (first 16 chars for readability)
    """
    if isinstance(data, str):
        content = data
    else:
        # Ensure stable serialization for dicts
        content = json.dumps(data, sort_keys=True, ensure_ascii=False)
    
    return hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]


class FileCache:
    """Simple file-based cache for generated artifacts.
    
    Cache structure:
        cache_dir/
            {cache_key}.{extension}  # Cached file
            {cache_key}.meta.json    # Metadata (optional)
    """
    
    def __init__(self, cache_dir: Optional[str] = None, enabled: bool = True):
        """Initialize file cache.
        
        Args:
            cache_dir: Directory to store cached files (default: workspace/cache)
            enabled: Whether caching is enabled (can disable via env)
        """
        self.cache_dir = Path(cache_dir or os.getenv("CACHE_DIR") or "workspace/cache")
        self.enabled = enabled and os.getenv("CACHE_ENABLED", "true").lower() != "false"
        
        if self.enabled:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
    
    def get(self, key: str, extension: str = "") -> Optional[str]:
        """Get cached file path if it exists.
        
        Args:
            key: Cache key (hash)
            extension: File extension (e.g., '.mp3', '.png')
            
        Returns:
            Path to cached file if exists, None otherwise
        """
        if not self.enabled:
            return None
        
        cache_file = self.cache_dir / f"{key}{extension}"
        if cache_file.exists():
            return str(cache_file)
        return None
    
    def put(
        self, 
        key: str, 
        file_path: str, 
        extension: str = "",
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """Store a file in cache.
        
        Args:
            key: Cache key (hash)
            file_path: Path to file to cache
            extension: File extension to use in cache
            metadata: Optional metadata to store alongside file
            
        Returns:
            Path to cached file
        """
        if not self.enabled:
            return file_path
        
        cache_file = self.cache_dir / f"{key}{extension}"
        
        # Copy file to cache (or move if in temp)
        import shutil
        shutil.copy(file_path, cache_file)
        
        # Store metadata if provided
        if metadata:
            meta_file = self.cache_dir / f"{key}.meta.json"
            meta_file.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
        
        return str(cache_file)
    
    def get_metadata(self, key: str) -> Optional[Dict[str, Any]]:
        """Get metadata for a cached item.
        
        Args:
            key: Cache key
            
        Returns:
            Metadata dict if exists, None otherwise
        """
        if not self.enabled:
            return None
        
        meta_file = self.cache_dir / f"{key}.meta.json"
        if meta_file.exists():
            return json.loads(meta_file.read_text(encoding="utf-8"))
        return None
    
    def clear(self) -> int:
        """Clear all cached files.
        
        Returns:
            Number of files removed
        """
        if not self.enabled or not self.cache_dir.exists():
            return 0
        
        count = 0
        for file in self.cache_dir.iterdir():
            if file.is_file():
                file.unlink()
                count += 1
        return count
