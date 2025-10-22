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
python -m agent.cli input.md --full-pipeline --out output/
```

**Key Flags**:
- `--full-pipeline`: Run complete pipeline (script + compose + merge)
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
1. Sends chapter to Google Gemini for slide plan
2. Generates image for each slide (Google Imagen)
3. Synthesizes audio for narration (Google Cloud TTS)
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
- Parse JSON responses using `json_repair` library
- Handle rate limiting

**Main Classes**:
```python
class LLMClient:
    def call(prompt: str) -> str
    def call_with_retry(prompt: str, max_retries: int) -> str
    def validate_json_response(response: str) -> dict
```

**JSON Parsing**:
- Uses `json_repair` library to handle malformed JSON from LLMs
- Automatically fixes common errors (missing quotes, trailing commas, etc.)
- Significantly reduces retry attempts due to parse failures
- See `docs/JSON_PARSING_IMPROVEMENTS.md` for details

**Retry Strategy**:
- Exponential backoff: 1s, 2s, 4s, 8s, etc.
- Configurable max retries (default: 3)
- Partial failure tolerance

**Example Usage**:
```python
from agent.google import GoogleServices

services = GoogleServices()
client = LLMClient(llm_provider=services)
response = client.generate_and_validate(
    chapter_text="Introduction to Python",
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

## Google Services Integration

### Architecture (`agent/google/`)

The system uses a **unified Google Services integration** for all AI capabilities:

```python
class GoogleServices:
    """Unified Google AI services for LLM, TTS, and image generation."""
    
    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.getenv("GOOGLE_API_KEY")
        self.genai_client = genai.Client(api_key=self.api_key)
    
    def generate_slide_plan(self, chapter_text: str) -> dict:
        """Generate slide plan using Google Gemini."""
        # Uses Gemini model via google-genai SDK
        
    def synthesize_speech(self, text: str) -> bytes:
        """Synthesize speech using Google Cloud TTS."""
        # Uses Cloud Text-to-Speech API
        
    def generate_image(self, prompt: str) -> bytes:
        """Generate image using Google Imagen 3.0."""
        # Uses Imagen via google-genai SDK
```

**Location**: `agent/google/services.py`

---

### GoogleServices (`agent/google/services.py`)

**Purpose**: Unified interface to all Google AI services

**Configuration**:
```bash
export GOOGLE_API_KEY=your-api-key-here
```

**Capabilities**:
- **LLM**: Google Gemini (gemini-2.0-flash-exp, gemini-1.5-pro)
- **TTS**: Google Cloud Text-to-Speech (multiple voices)
- **Image**: Google Imagen 3.0 (fast-mode, high quality)

**Cost** (approximate):
- Gemini: ~$0.001-0.01 per slide
- Cloud TTS: ~$0.000004 per character
- Imagen: ~$0.01-0.04 per image

**Usage**:
```python
from agent.google import GoogleServices

services = GoogleServices()
slides = services.generate_slide_plan("Chapter about Python")
audio = services.synthesize_speech("Hello world")
image = services.generate_image("A python snake coding")
```

---

### TTS Adapters (`agent/google/tts.py`)

**GoogleTTSAdapter**: Production Google Cloud TTS integration

**Configuration**:
```bash
export GOOGLE_API_KEY=your-api-key-here
# Optional: GOOGLE_APPLICATION_CREDENTIALS for service account
```

**Features**:
- High-quality neural voices
- Multiple languages
- SSML support
- Cached results

**DummyTTSAdapter**: Testing/development fallback

**Features**:
- No API calls
- Instant response
- Fixed-duration mock audio
- Perfect for development

**Usage**:
```python
from agent.google import get_tts_adapter

adapter = get_tts_adapter()  # Returns GoogleTTSAdapter or DummyTTSAdapter
audio_bytes = adapter.synthesize("Hello world")
```

---

### Image Adapters (`agent/google/image.py`)

**DummyImageAdapter**: Testing/development implementation

**Purpose**: Generate placeholder images without API calls

**Features**:
- Instant generation
- Text-based placeholders
- No cost
- Ideal for testing

**Usage**:
```python
from agent.google.image import DummyImageAdapter

adapter = DummyImageAdapter()
image_bytes = adapter.generate("A beautiful landscape")
```

**Note**: Production image generation uses `GoogleServices.generate_image()` method directly via Imagen 3.0.

---

### Storage (`agent/google/storage.py`)

**DummyStorageAdapter**: Local file storage implementation

**Purpose**: Store artifacts locally with `file://` URLs

**Features**:
- Local filesystem storage
- No cloud dependencies
- Simple upload/download
- Perfect for development

**Configuration**: No configuration needed (uses local paths)

**Usage**:
```python
from agent.google import get_storage_adapter

storage = get_storage_adapter()
url = storage.upload_file("/path/to/file.mp4")  # Returns: file:///path/to/file.mp4
local_path = storage.download_file(url)
```

**Production**: For production use, integrate Cloud Storage SDK directly as needed

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

## Extending the System

### Adding Custom Processing

While the system is Google-centric, you can extend functionality:

**Option 1: Extend GoogleServices class**
```python
# agent/google/services.py
class GoogleServices:
    def custom_processing(self, data):
        # Add custom logic here
        pass
```

**Option 2: Create custom pipeline nodes**
```python
# agent/langgraph_nodes.py
def custom_node(state: dict) -> dict:
    # Process state
    return updated_state
```

**Option 3: Add post-processing hooks**
```python
# agent/video_composer.py
def add_custom_effects(video_path: str):
    # Add custom video effects
    pass
```

### Integration with Other Services

If you need to integrate non-Google services:

1. Create adapter in `agent/google/` directory
2. Follow existing patterns (DummyTTSAdapter, DummyImageAdapter)
3. Add factory function like `get_tts_adapter()`
4. Update configuration in environment variables

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
