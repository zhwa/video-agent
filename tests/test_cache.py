import os
from pathlib import Path
from agent.cache import compute_cache_key, FileCache


def test_compute_cache_key():
    """Test that cache keys are stable and deterministic."""
    # String input
    key1 = compute_cache_key("hello world")
    key2 = compute_cache_key("hello world")
    assert key1 == key2
    assert len(key1) == 16  # First 16 chars of SHA256
    
    # Different strings produce different keys
    key3 = compute_cache_key("different text")
    assert key1 != key3
    
    # Dict input (with stable sorting)
    key4 = compute_cache_key({"b": 2, "a": 1})
    key5 = compute_cache_key({"a": 1, "b": 2})
    assert key4 == key5  # Order shouldn't matter


def test_file_cache_basic(tmp_path):
    """Test basic file cache operations."""
    cache_dir = tmp_path / "cache"
    cache = FileCache(cache_dir=str(cache_dir))
    
    # Create a test file
    test_file = tmp_path / "test.txt"
    test_file.write_text("Hello cache!", encoding="utf-8")
    
    # Put in cache
    key = "test_key"
    cached_path = cache.put(key, str(test_file), extension=".txt")
    assert os.path.exists(cached_path)
    assert Path(cached_path).read_text(encoding="utf-8") == "Hello cache!"
    
    # Get from cache
    retrieved = cache.get(key, extension=".txt")
    assert retrieved == cached_path
    assert Path(retrieved).read_text(encoding="utf-8") == "Hello cache!"


def test_file_cache_with_metadata(tmp_path):
    """Test cache with metadata storage."""
    cache_dir = tmp_path / "cache"
    cache = FileCache(cache_dir=str(cache_dir))
    
    test_file = tmp_path / "test.txt"
    test_file.write_text("test", encoding="utf-8")
    
    key = "meta_test"
    metadata = {"author": "test", "version": "1.0"}
    
    cache.put(key, str(test_file), extension=".txt", metadata=metadata)
    
    # Retrieve metadata
    retrieved_meta = cache.get_metadata(key)
    assert retrieved_meta == metadata


def test_file_cache_miss(tmp_path):
    """Test cache miss returns None."""
    cache = FileCache(cache_dir=str(tmp_path / "cache"))
    
    # Non-existent key
    result = cache.get("nonexistent", extension=".txt")
    assert result is None


def test_file_cache_disabled(tmp_path):
    """Test that disabled cache doesn't cache."""
    cache = FileCache(cache_dir=str(tmp_path / "cache"), enabled=False)
    
    test_file = tmp_path / "test.txt"
    test_file.write_text("test", encoding="utf-8")
    
    # Put should return original path
    result = cache.put("key", str(test_file), extension=".txt")
    assert result == str(test_file)
    
    # Get should return None
    assert cache.get("key", extension=".txt") is None


def test_file_cache_clear(tmp_path):
    """Test cache clearing."""
    cache_dir = tmp_path / "cache"
    cache = FileCache(cache_dir=str(cache_dir))
    
    # Add some files
    for i in range(3):
        test_file = tmp_path / f"test{i}.txt"
        test_file.write_text(f"test{i}", encoding="utf-8")
        cache.put(f"key{i}", str(test_file), extension=".txt")
    
    # Verify files exist
    assert len(list(cache_dir.iterdir())) == 3
    
    # Clear cache
    count = cache.clear()
    assert count == 3
    assert len(list(cache_dir.iterdir())) == 0


def test_file_cache_env_disabled(tmp_path, monkeypatch):
    """Test cache can be disabled via environment variable."""
    monkeypatch.setenv("CACHE_ENABLED", "false")
    
    cache = FileCache(cache_dir=str(tmp_path / "cache"))
    assert not cache.enabled
    
    test_file = tmp_path / "test.txt"
    test_file.write_text("test", encoding="utf-8")
    
    # Should not cache
    result = cache.get("key", extension=".txt")
    assert result is None
