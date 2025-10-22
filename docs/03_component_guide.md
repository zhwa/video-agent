# Chapter 3: Component Guide

Comprehensive reference for all major components in the Video Agent pipeline.

---

## Core Pipeline Components

### 1. CLI (`agent/cli.py`)

**Purpose**: Command-line interface and entry point for the entire pipeline.

**Key Responsibilities**:
- Parse command-line arguments
- Validate input files
- Initialize configuration
- Orchestrate pipeline execution
- Handle output and error reporting

**Main Functions**:
```python
def main()              # Entry point, parses CLI args
def compose_workflow()  # Composes per-chapter videos
def merge_workflow()    # Merges all videos
```

**Common Usage**:
```bash
python -m agent.cli input.md --full-pipeline --out output/ --provider openai
```

**Key Flags**:
- `--full-pipeline`: Run complete pipeline (script + compose + merge)
- `--provider`: LLM provider (vertex, openai, dummy)
- `--max-workers`: Parallel chapter workers
- `--resume`: Resume from checkpoint

---

### 2. Segmenter (`agent/segmenter.py`)

**Purpose**: Extracts chapters/sections from input documents (PDF or Markdown).

**Key Responsibilities**:
- Parse document structure
- Extract chapter titles and content
- Handle different document formats
- Validate chapter structure

**Main Classes**:
```python
class DocumentSegmenter:
    def segment(document_path: str) -> List[Chapter]
    def validate_chapters() -> bool
```

**Supported Formats**:
- Markdown (`.md`) - Uses `#` headers for chapters
- PDF (`.pdf`) - Uses document structure

**Example Output**:
```python
[
    Chapter(title="Introduction", content="..."),
    Chapter(title="Main Topic", content="..."),
]
```

---

### 3. Script Generator (`agent/script_generator.py`)

**Purpose**: Orchestrates slide generation using LLM and creates audio/images.

**Key Responsibilities**:
- Generate slide plans for each chapter
- Create speaker notes
- Generate images for slides
- Synthesize audio narration

**Main Classes**:
```python
class ScriptGenerator:
    def generate_script(chapter: Chapter) -> ChapterScript
    def generate_slides(chapter: Chapter) -> List[Slide]
```

**Workflow**:
1. Sends chapter to LLM for slide plan
2. Generates image for each slide (Image adapter)
3. Synthesizes audio for narration (TTS adapter)
4. Returns complete script with all media

**Output Structure**:
```python
ChapterScript(
    chapter_id="ch_01",
    slides=[
        Slide(text="...", image_url="...", audio_url="..."),
        ...
    ],
    metadata={...}
)
```

---

### 4. LLM Client (`agent/llm_client.py`)

**Purpose**: Wrapper around LLM adapters with retry logic and output validation.

**Key Responsibilities**:
- Retry failed requests with exponential backoff
- Validate LLM output format
- Parse JSON responses
- Handle rate limiting

**Main Classes**:
```python
class LLMClient:
    def call(prompt: str) -> str
    def call_with_retry(prompt: str, max_retries: int) -> str
    def validate_json_response(response: str) -> dict
```

**Retry Strategy**:
- Exponential backoff: 1s, 2s, 4s, 8s, etc.
- Configurable max retries (default: 3)
- Partial failure tolerance

**Example Usage**:
```python
client = LLMClient(provider="openai")
response = client.call_with_retry(
    prompt="Generate 3 slides about Python",
    max_retries=3
)
```

---

### 5. Video Composer (`agent/video_composer.py`)

**Purpose**: Assembles video from slides, audio, and images using moviepy.

**Key Responsibilities**:
- Load audio/image files
- Synchronize audio with slide timing
- Generate subtitles
- Create final MP4 video
- Apply transitions

**Main Classes**:
```python
class VideoComposer:
    def compose_chapter(script: ChapterScript) -> str
    def add_subtitles(video_path: str, subtitles: List[Subtitle]) -> str
```

**Workflow**:
1. Load all slide images
2. Synchronize with audio duration
3. Calculate slide timing
4. Compose video clip
5. Add transitions
6. Overlay subtitles
7. Write MP4 file

**Output**: MP4 file in `workspace/out/videos/`

---

### 6. Cache System (`agent/cache.py`)

**Purpose**: Content-based caching to avoid redundant API calls.

**Key Responsibilities**:
- Generate content hash
- Store artifacts (images, audio)
- Retrieve cached results
- Manage cache expiration

**Main Classes**:
```python
class Cache:
    def get(key: str) -> Optional[str]
    def set(key: str, value: str, metadata: dict) -> None
    def exists(key: str) -> bool
```

**Cache Key Strategy**:
- Hash-based on content (deterministic)
- Enables resume without API calls
- Survives across runs

**Cached Artifacts**:
- Generated images (`.png`)
- Audio files (`.mp3`)
- Metadata (`.meta.json`)

**Performance Impact**:
- 60%+ speedup when 80%+ of artifacts cached
- Significant cost reduction for expensive APIs

---

### 7. Runs/Checkpointing (`agent/runs.py`)

**Purpose**: Saves run state for resuming interrupted pipelines.

**Key Responsibilities**:
- Save chapter progress
- Checkpoint intermediate results
- Enable resume from any chapter
- Track run metadata

**Main Classes**:
```python
class RunManager:
    def save_checkpoint(run_id: str, checkpoint: dict) -> None
    def load_checkpoint(run_id: str) -> dict
    def list_runs() -> List[RunInfo]
```

**Checkpoint Structure**:
```
workspace/runs/
├── run_id_abc123/
│   ├── metadata.json          # Run info
│   ├── checkpoint.json         # Current state
│   └── chapter_results/        # Per-chapter outputs
│       ├── chapter_01.json
│       └── chapter_02.json
```

**Resume Workflow**:
```bash
python -m agent.cli input.md --full-pipeline --resume run_id_abc123
```

---

### 8. Telemetry (`agent/telemetry.py`)

**Purpose**: Unified logging and observability across the pipeline.

**Key Responsibilities**:
- Structured logging
- API call tracking
- Performance metrics
- Error reporting

**Main Capabilities**:
```python
logger.info("Processing chapter 1")
logger.debug("LLM request: %s", prompt)
logger.error("Failed to generate image", exc_info=True)
```

**Output**:
- Console output (INFO+)
- Debug logs (optional, in `workspace/llm_logs/`)
- Structured JSON logs

---

## Adapter System

### Architecture

The adapter system uses **Factory Pattern** to support multiple providers:

```python
class LLMAdapter:
    def call(prompt: str) -> str  # Abstract method

class OpenAIAdapter(LLMAdapter):
    def call(prompt: str) -> str  # OpenAI implementation

class VertexAdapter(LLMAdapter):
    def call(prompt: str) -> str  # Vertex AI implementation

class DummyAdapter(LLMAdapter):
    def call(prompt: str) -> str  # Mock implementation
```

### Factory (`agent/adapters/factory.py`)

**Purpose**: Creates appropriate adapter based on configuration.

```python
adapter = AdapterFactory.create_llm_adapter(provider="openai")
# Returns: OpenAIAdapter instance
```

**Graceful Fallback**:
- If provider not available → uses DummyAdapter
- Allows testing without credentials
- Non-blocking failures

---

### LLM Adapters

#### OpenAI (`agent/adapters/openai_adapter.py`)

**Provider**: OpenAI API (GPT-4, GPT-3.5)

**Configuration**:
```bash
export OPENAI_API_KEY=sk-...
export LLM_PROVIDER=openai
```

**Capabilities**:
- Full LLM access
- Structured output support
- Function calling
- Vision (with multimodal models)

**Cost**: ~$0.01-0.10 per slide

---

#### Vertex AI (`agent/adapters/google_vertex_adapter.py`)

**Provider**: Google Cloud Vertex AI (PaLM, Gemini)

**Configuration**:
```bash
export GOOGLE_APPLICATION_CREDENTIALS=/path/to/credentials.json
export LLM_PROVIDER=vertex
```

**Capabilities**:
- Multimodal models
- Low latency
- Enterprise security

**Cost**: ~$0.001-0.01 per slide

---

#### Dummy (`agent/adapters/`)

**Provider**: Mock/test implementation (no credentials needed)

**Features**:
- Instant response
- Deterministic output
- Perfect for testing/development

**Usage**:
```bash
# Automatically used when provider unavailable
python -m agent.cli input.md --full-pipeline
```

---

### TTS Adapters

#### Google Cloud TTS (`agent/adapters/`)

**Provider**: Google Cloud Text-to-Speech

**Configuration**:
```bash
export TTS_PROVIDER=google
export GOOGLE_APPLICATION_CREDENTIALS=/path/to/credentials.json
```

**Output**: High-quality audio (MP3/WAV)

**Cost**: ~$0.000004 per character

---

#### ElevenLabs (`agent/adapters/elevenlabs_tts.py`)

**Provider**: ElevenLabs API

**Configuration**:
```bash
export TTS_PROVIDER=elevenlabs
export ELEVENLABS_API_KEY=...
```

**Features**:
- Natural-sounding voice
- Multiple voice options
- Emotional control

**Cost**: ~$0.30 per 10K characters

---

### Image Adapters

#### Stability AI (`agent/adapters/stability_adapter.py`)

**Provider**: Stability AI (SDXL)

**Configuration**:
```bash
export IMAGE_PROVIDER=stability
export STABILITY_API_KEY=...
```

**Output**: High-quality images (512x512 to 2048x2048)

**Cost**: ~$0.02 per image

---

#### Replicate (`agent/adapters/replicate_adapter.py`)

**Provider**: Replicate API

**Configuration**:
```bash
export IMAGE_PROVIDER=replicate
export REPLICATE_API_TOKEN=...
```

**Models**: SDXL, Stable Diffusion, etc.

**Cost**: ~$0.001-0.01 per image (model dependent)

---

### Storage Adapters

#### Google Cloud Storage (`agent/storage/gcs_adapter.py`)

**Purpose**: Store generated artifacts in GCS bucket

**Configuration**:
```bash
export STORAGE_PROVIDER=gcs
export GCS_BUCKET=my-bucket
```

**Usage**: Automatic artifact upload after generation

---

#### MinIO (`agent/storage/minio_adapter.py`)

**Purpose**: S3-compatible storage (MinIO, AWS S3, DigitalOcean Spaces)

**Configuration**:
```bash
export STORAGE_PROVIDER=minio
export MINIO_ENDPOINT=minio.example.com:9000
export MINIO_ACCESS_KEY=minioadmin
export MINIO_SECRET_KEY=minioadmin
```

---

## Workflow Engine

### LangGraph Integration (`agent/langgraph_graph.py`, `agent/langgraph_nodes.py`)

**Purpose**: Orchestrates pipeline as directed acyclic graph (DAG).

**Pipeline Stages**:
```
Input → Ingest → Segment → Script Gen → Compose → Merge → Output
```

**Key Features**:
- Parallel processing within stages
- State management
- Error recovery
- Conditional routing

**Example State**:
```python
{
    "input_file": "lecture.md",
    "chapters": [...],
    "scripts": [...],
    "videos": [...],
}
```

---

## Data Structures

### Chapter
```python
class Chapter:
    id: str                    # Unique identifier
    title: str                 # Chapter title
    content: str               # Chapter content
    order: int                 # Position in document
```

### Slide
```python
class Slide:
    title: str                 # Slide title
    content: str               # Speaker notes
    image_path: str            # Generated image
    audio_path: str            # Generated audio
    duration: float            # Audio duration in seconds
```

### ChapterScript
```python
class ChapterScript:
    chapter_id: str            # Reference to chapter
    slides: List[Slide]        # All slides
    duration: float            # Total duration
    metadata: dict             # Additional data
```

---

## Configuration Files

### YAML Configuration (`config/providers.example.yaml`)

```yaml
llm:
  provider: openai
  model: gpt-4
  max_retries: 3
  timeout: 30

tts:
  provider: google
  voice: "en-US-Neural2-C"

image:
  provider: stability
  model: sdxl
  
storage:
  provider: gcs
  bucket: my-bucket

processing:
  max_workers: 4
  max_slide_workers: 2
  cache_enabled: true
```

---

## Testing Components

Each component has comprehensive tests:

- `test_script_generator.py` - Script generation
- `test_video_composer.py` - Video composition
- `test_llm_client.py` - LLM client retry logic
- `test_cache.py` - Cache system
- `test_*_adapter.py` - Individual adapters

**Running Component Tests**:
```bash
pytest tests/test_script_generator.py -v
pytest tests/test_video_composer.py -v
```

---

## Performance Optimization

### Parallel Processing

```bash
# Process multiple chapters in parallel
python -m agent.cli input.md --max-workers 4 --full-pipeline

# Process multiple slides per chapter in parallel
python -m agent.cli input.md --max-slide-workers 2 --full-pipeline
```

**Impact**: ~3-4x speedup with 4 workers

### Rate Limiting

```bash
# Limit API calls to avoid rate limits
export SLIDE_RATE_LIMIT=10  # Max 10 calls/second
python -m agent.cli input.md --full-pipeline
```

### Caching

```bash
# Enable caching (default: enabled)
export CACHE_ENABLED=true
export CACHE_DIR=workspace/cache

# Subsequent runs reuse cached artifacts
python -m agent.cli input.md --full-pipeline  # First run: 5 min
python -m agent.cli input.md --full-pipeline  # Second run: 30 sec
```

---

## Adding Custom Components

### Adding a New LLM Provider

1. Create `agent/adapters/my_provider_adapter.py`:
```python
from agent.adapters.llm import LLMAdapter

class MyProviderAdapter(LLMAdapter):
    def call(self, prompt: str) -> str:
        # Your implementation
        pass
```

2. Register in factory (`agent/adapters/factory.py`):
```python
if provider == "my_provider":
    return MyProviderAdapter()
```

3. Set environment variable:
```bash
export LLM_PROVIDER=my_provider
```

### Adding a New Storage Backend

1. Create `agent/storage/my_storage_adapter.py`:
```python
from agent.storage.schema import StorageAdapter

class MyStorageAdapter(StorageAdapter):
    def upload(self, local_path: str) -> str:
        # Your implementation
        pass
```

2. Register in factory
3. Set environment variable

---

## Common Debugging

### Enable Debug Logging

```bash
export LOG_LEVEL=DEBUG
python -m agent.cli input.md --llm-out workspace/llm_logs/ --full-pipeline
```

### Inspect LLM Responses

```bash
cat workspace/llm_logs/attempt_01_response.txt
```

### Check Cache Status

```bash
ls -la workspace/cache/
```

### Resume with Debug

```bash
python -m agent.cli input.md --full-pipeline --resume RUN_ID --max-workers 1
```

---

**Next**: See [Chapter 4: Deployment](04_deployment.md) for production setup.
