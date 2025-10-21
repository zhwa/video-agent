# Appendix A — Caching & Performance Optimization

This appendix covers the caching system that improves performance by avoiding regeneration of slides, audio, and images.

## Why Caching Matters

**Problem**: Video generation is expensive
- Each slide generation costs LLM API tokens
- Each image costs compute credits
- Each audio synthesis takes time
- Regenerating the same content is wasteful

**Solution**: Cache results by content hash

```
Input: "Generate a slide about Python"
  ↓ 
  SHA256 hash → "a1b2c3d4"
  ↓
  Check cache: Does "a1b2c3d4" exist?
  ↓
  Yes → Return cached file
  No → Generate new, save to cache
```

---

## FileCache Implementation

### Architecture

```python
FileCache stores files by hash:

workspace/cache/
  ├── a1b2c3d4.mp3           # Cached audio
  ├── a1b2c3d4.meta.json     # Metadata (optional)
  ├── e5f6g7h8.png           # Cached image
  ├── e5f6g7h8.meta.json     # Metadata
  └── ...
```

### Code Structure

```python
# agent/cache.py

class FileCache:
    def __init__(self, cache_dir="workspace/cache", enabled=True):
        self.cache_dir = Path(cache_dir)
        self.enabled = enabled
        
    def get(self, key: str, extension: str = "") -> Optional[str]:
        """Get cached file if exists"""
        # Returns: /path/to/cache/a1b2c3d4.mp3
        
    def put(self, key: str, file_path: str, extension: str = "", 
            metadata: Dict = None) -> str:
        """Store file in cache"""
        # Copies file to cache, stores metadata
        # Returns: /path/to/cache/a1b2c3d4.mp3
        
    def get_metadata(self, key: str) -> Optional[Dict]:
        """Get metadata for cached file"""
        
    def clear(self) -> int:
        """Clear all cached files"""
```

### Cache Key Generation

```python
def compute_cache_key(data: Any) -> str:
    """Create stable hash of data
    
    Why stable? Same input always produces same hash
    """
    if isinstance(data, str):
        content = data
    else:
        # Sort keys for deterministic JSON
        content = json.dumps(data, sort_keys=True, ensure_ascii=False)
    
    return hashlib.sha256(content.encode()).hexdigest()[:16]

# Examples:
compute_cache_key("Generate slide about Python")
  → "a1b2c3d4e5f6g7h8"

compute_cache_key({"title": "Python", "bullets": ["A", "B"]})
  → "a1b2c3d4e5f6g7h8"  (same every time)
```

---

## Usage Examples

### Audio Caching

```python
from agent.cache import FileCache, compute_cache_key

cache = FileCache()

# Generate cache key from text
text = "Welcome to Python programming"
cache_key = compute_cache_key(text)

# Check cache
cached_audio = cache.get(cache_key, extension=".mp3")
if cached_audio:
    print(f"Using cached audio: {cached_audio}")
else:
    # Generate new audio
    tts = get_tts_adapter()
    audio_path = tts.synthesize(text)
    
    # Save to cache
    cached = cache.put(
        cache_key, 
        audio_path, 
        extension=".mp3",
        metadata={"text": text, "provider": "elevenlabs"}
    )
    print(f"Saved to cache: {cached}")
```

### Image Caching

```python
# Cache image generation
prompt = "Professional office with Python code"
cache_key = compute_cache_key(prompt)

cached_image = cache.get(cache_key, extension=".png")
if not cached_image:
    image_adapter = get_image_adapter()
    image_path = image_adapter.generate_image(prompt)
    
    cached = cache.put(
        cache_key,
        image_path,
        extension=".png",
        metadata={"prompt": prompt, "provider": "stability"}
    )
```

### Slide Generation Caching

```python
# LLMClient uses caching internally
from agent.llm_client import LLMClient

client = LLMClient(timeout=30)

# First call: generates via LLM
result1 = client.generate_and_validate(adapter, chapter_text)

# Second call with same text: uses cache
result2 = client.generate_and_validate(adapter, chapter_text)
# Returns immediately (cached)
```

---

## Metadata Storage

Metadata enables rich cache queries:

```python
# Store metadata with cached file
cache.put(
    key="a1b2c3d4",
    file_path="/tmp/audio.mp3",
    extension=".mp3",
    metadata={
        "text": "Welcome",
        "provider": "elevenlabs",
        "voice_id": "21m00Tcm4TlvDq8ikWAM",
        "timestamp": "2024-01-15T10:30:00",
        "duration_sec": 2.5
    }
)

# Retrieve metadata
meta = cache.get_metadata("a1b2c3d4")
print(meta["duration_sec"])  # → 2.5
```

---

## Cache Control

### Enable/Disable Caching

```bash
# Enable caching (default)
export CACHE_ENABLED="true"

# Disable caching
export CACHE_ENABLED="false"

# Or in code
cache = FileCache(enabled=False)
```

### Custom Cache Directory

```bash
# Set cache directory
export CACHE_DIR="/data/video-cache"

# Or in code
cache = FileCache(cache_dir="/data/video-cache")
```

### Clear Cache

```bash
# Programmatically
cache = FileCache()
count = cache.clear()
print(f"Removed {count} files")

# Or manually
rm -rf workspace/cache/*
```

---

## Cache Hit/Miss Performance

### Benchmarks

```
Cache HIT (file retrieved):
  - Time: ~50ms
  - I/O: Single file read
  - Cost: ~0 API tokens

Cache MISS (must generate):
  - TTS generation: 2-5 seconds + API call
  - Image generation: 5-30 seconds + API call
  - LLM generation: 3-10 seconds + API call
  - Cost: 100-5000 tokens (varies by provider)

With caching, 80% of calls hit cache:
  Before: 100 slides × 5 sec = 500 seconds
  After:  80 cached + 20 generated = 100 + 100 = 200 seconds
  Improvement: 60% faster
```

### Improving Cache Hit Rate

```python
# 1. Normalize input text (removes variation)
text = chapter_text.strip().lower()
text = re.sub(r'\s+', ' ', text)  # Normalize whitespace

# 2. Use deterministic formatting
# ✅ Good:
cache_key = compute_cache_key(text)

# ❌ Bad:
cache_key = str(hash(text))  # Not deterministic across runs

# 3. Cache at the right level
# For TTS: cache by text (not by slide)
# For images: cache by prompt
# For slides: cache by chapter text
```

---

## When NOT to Use Cache

⚠️ **Don't cache**:
- User session data
- Sensitive information (passwords, keys)
- Real-time data (prices, weather)
- Mutable state

✅ **Do cache**:
- LLM slide generation
- Audio synthesis
- Image generation
- Configuration validation

---

## Cache Invalidation

The hardest problem in computer science:

### Strategy 1: Time-Based Expiration
```python
def get_with_ttl(key: str, ttl_seconds: int = 86400) -> Optional[str]:
    cached = cache.get(key)
    if not cached:
        return None
    
    meta = cache.get_metadata(key)
    if not meta:
        return cached
    
    age = time.time() - meta.get("timestamp", 0)
    if age > ttl_seconds:
        return None  # Expired
    
    return cached
```

### Strategy 2: Version-Based
```python
def get_versioned(key: str, version: str) -> Optional[str]:
    versioned_key = f"{key}_v{version}"
    return cache.get(versioned_key)

# When data format changes:
get_versioned("chapter_slides", version="2")
# Avoids old version incompatibilities
```

### Strategy 3: Content-Hash Based (Current)
```python
# Current approach:
# - Input doesn't change → hash doesn't change → cache hit
# - Input changes → hash changes → cache miss
# - No explicit invalidation needed
```

---

## Debugging Cache Issues

### Check what's cached
```python
import os
cache_dir = "workspace/cache"
files = os.listdir(cache_dir)
print(f"Cached {len(files)} files")
for f in files:
    print(f"  {f}")
```

### Check cache hit rate
```python
hits = 0
misses = 0

def instrumented_cache_get(key, extension=""):
    global hits, misses
    result = cache.get(key, extension)
    if result:
        hits += 1
    else:
        misses += 1
    return result

# After run:
print(f"Cache hits: {hits}")
print(f"Cache misses: {misses}")
print(f"Hit rate: {100*hits/(hits+misses):.1f}%")
```

### Verify cache integrity
```python
import json

for f in os.listdir(cache_dir):
    if f.endswith(".meta.json"):
        path = os.path.join(cache_dir, f)
        try:
            meta = json.load(open(path))
            print(f"✓ {f}")
        except json.JSONDecodeError:
            print(f"✗ {f} CORRUPTED")
```

---

## Next Steps

- See [Chapter 4: Code Walkthrough](chapter4_code_walkthrough.md) for caching usage
- See [Chapter 5: Design Patterns](chapter5_design_patterns.md) for pattern analysis
- See [Chapter 8: Testing Strategies](chapter8_testing_strategies.md) for cache testing

