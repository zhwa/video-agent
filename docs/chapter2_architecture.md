# Chapter 2 — Architecture & System Design

## High-Level Pipeline

The system transforms lecture content through a series of processing stages:

```
Input File (MD/PDF)
    ↓
[Ingestion Layer]
    ↓ Read and normalize content
[Segmentation Layer]
    ↓ Split into chapters
[Script Generation]
    ↓ LLM creates structured slides
[Asset Generation]
    ↓ Parallel: TTS audio + Images
[Video Composition]
    ↓ Per-chapter MP4 files
[Merge]
    ↓ Final course video
```

## Module Organization

### Core Orchestration
- **cli.py**: Entry point, argument parsing, main orchestration
- **langgraph_graph.py**: Ingestion and segmentation orchestration
- **langgraph_nodes.py**: LangGraph-style node definitions and runner

### Processing Modules
- **script_generator.py**: LLM-based slide generation with retries and validation
- **video_composer.py**: MoviePy-based video composition
- **parallel.py**: Thread pool utilities and rate limiting
- **cache.py**: Result caching for optimization
- **runs.py** & **runs_safe.py**: Checkpoint management with thread safety

### Input/Output
- **io.py**: File reading (PDF, Markdown, directory listing)
- **segmenter.py**: Chapter segmentation logic

### Adapters (Pluggable)
- **adapters/factory.py**: Centralized adapter creation (factory pattern)
- **adapters/schema.py**: Abstract base classes for all adapters
- **adapters/llm.py**: LLM adapter interface
- **adapters/openai_adapter.py**: OpenAI implementation
- **adapters/google_vertex_adapter.py**: Google Vertex AI implementation
- **adapters/tts.py**: TTS adapter interface
- **adapters/elevenlabs_tts.py**: ElevenLabs TTS implementation
- **adapters/image.py**: Image generation adapter interface
- **adapters/stability_adapter.py**: Stability AI implementation
- **adapters/replicate_adapter.py**: Replicate implementation
- **adapters/embeddings.py**: Embeddings adapter interface
- **adapters/vector_db.py**: Vector DB adapter interface
- **adapters/json_utils.py**: Shared JSON extraction utilities (Phase 3)

### Storage (Pluggable)
- **storage/dummy_storage.py**: No-op storage for testing
- **storage/gcs_adapter.py**: Google Cloud Storage
- **storage/minio_adapter.py**: MinIO S3-compatible storage

### Utilities
- **log_config.py**: Logging configuration
- **telemetry.py**: Basic instrumentation
- **llm_client.py**: LLM retry logic and validation

## Data Flow Example

### Input → Processing → Output

```
Input: lecture.md
├─ Read markdown file (io.py)
├─ Parse into chapters (segmenter.py)
├─ For each chapter:
│  ├─ Generate script via LLM (script_generator.py)
│  │  ├─ With retries on failure (llm_client.py)
│  │  ├─ With validation (schema.py)
│  │  └─ Store in checkpoint (runs.py)
│  ├─ Generate assets in parallel:
│  │  ├─ TTS audio for each slide (adapters/tts.py)
│  │  ├─ Images for descriptions (adapters/image.py)
│  │  └─ Rate-limited concurrent (parallel.py)
│  ├─ Compose chapter video (video_composer.py)
│  └─ Upload artifacts (storage/*)
├─ Merge all chapter videos
└─ Output: final_course.mp4
```

## Design Patterns Used

### 1. Factory Pattern
**Location**: `adapters/factory.py`

Single place to create and configure adapters:
```python
def get_llm_adapter(provider: Optional[str] = None) -> LLMAdapter:
    """Create appropriate LLM adapter based on provider"""
    # Resolves from parameter, environment, or defaults
    # Handles fallback to dummy implementation
```

### 2. Adapter Pattern
**Location**: `adapters/schema.py`, `adapters/*_adapter.py`

Define interfaces, implement for each provider:
```python
class LLMAdapter(ABC):
    @abstractmethod
    def generate(self, messages: List[Dict]) -> str: pass

class OpenAIAdapter(LLMAdapter):
    def generate(self, messages: List[Dict]) -> str: ...

class GoogleVertexAdapter(LLMAdapter):
    def generate(self, messages: List[Dict]) -> str: ...
```

### 3. Retry Pattern
**Location**: `llm_client.py`

Automatic retry with exponential backoff:
```python
def call_with_retries(func, max_retries=3, backoff_base=2):
    for attempt in range(max_retries):
        try:
            return func()
        except TransientError:
            if attempt == max_retries - 1:
                raise
            wait_time = backoff_base ** attempt
            time.sleep(wait_time)
```

### 4. Thread-Safe State
**Location**: `runs_safe.py`

File locking + atomic writes for concurrent access:
```python
lock_handle = _acquire_lock(lock_file, timeout=5.0)
try:
    # Read → Update → Write atomically
    temp_fd, temp_path = tempfile.mkstemp()
    os.replace(temp_path, final_path)  # Atomic rename
finally:
    _release_lock(lock_handle)
```

## Configuration Management

### Environment Variables
```bash
# LLM Configuration
LLM_PROVIDER=openai|vertex
OPENAI_API_KEY=sk-...
GOOGLE_APPLICATION_CREDENTIALS=/path/to/credentials.json

# TTS Configuration
TTS_PROVIDER=elevenlabs|google
ELEVENLABS_API_KEY=...

# Image Configuration
IMAGE_PROVIDER=stability|replicate
STABILITY_API_KEY=...

# Processing Configuration
MAX_WORKERS=4               # Concurrent workers
MAX_SLIDE_WORKERS=4        # Slide asset workers
SLIDE_RATE_LIMIT=2.0       # Calls/second
LLM_RATE_LIMIT=1.0         # API calls/second
MAX_COMPOSER_WORKERS=1     # Video composition workers
```

### Configuration File
```yaml
# config/providers.yaml
llm:
  provider: openai|vertex
  api_key: ${OPENAI_API_KEY}

tts:
  provider: elevenlabs
  api_key: ${ELEVENLABS_API_KEY}

image:
  provider: stability
  api_key: ${STABILITY_API_KEY}
```

## Error Handling Strategy

### Layered Approach

1. **Transport Layer** (API calls)
   - Retry on transient errors (timeouts, rate limits)
   - Fail fast on permanent errors (auth, not found)

2. **Validation Layer**
   - Validate API responses match expected schema
   - Log validation failures with context

3. **Application Layer**
   - Handle missing adapters with fallback to dummy
   - Continue processing even if one asset fails

4. **CLI Layer**
   - Catch and report errors to user
   - Exit with appropriate status code

## Thread Safety

### Problem Solved
Multiple parallel workers writing checkpoints could corrupt state.

### Solution
Atomic checkpoint operations:
1. Acquire exclusive file lock
2. Read current state
3. Update specific field
4. Write to temporary file
5. Atomic rename to final location
6. Release lock

### Guarantees
- Only one writer at a time
- Complete atomic writes (no partial writes)
- Timeout if lock unavailable (prevents deadlocks)
- Graceful fallback if locking fails

## Performance Considerations

### Parallelization Strategy

```
Script Generation: Sequential (LLM rate-limited)
Asset Generation: Parallel (TTS + Images concurrent)
Video Composition: Configurable (sequential or parallel)
```

### Rate Limiting
- Per-provider rate limits
- Token bucket algorithm for smooth limiting
- Prevents overwhelming external APIs

### Caching
- Cache generated slides to avoid regeneration
- Cache artifacts (audio, images) locally
- Resume from checkpoint on restart

## Deployment Considerations

### Minimal (Local)
- Uses dummy providers
- No API keys needed
- Runs offline
- Perfect for testing/learning

### With Real Providers
- Requires API credentials
- Can use any combination of providers
- Uploads artifacts to cloud storage
- Full video generation pipeline

### Scalability
- Horizontally: Spawn multiple workers
- Vertically: Increase worker threads
- Rate limiting prevents overwhelming APIs
- Checkpoints enable distributed resumption

## Next Steps

Learn about the [specific patterns used](#design-patterns-used) in [Chapter 5: Design Patterns](chapter5_design_patterns.md)

Or dive into [implementation details](chapter4_code_walkthrough.md)
