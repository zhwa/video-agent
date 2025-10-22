# Chapter 1: Architecture Overview

## System Design

The Video Agent is a sophisticated pipeline that transforms educational content (PDF/Markdown) into professional video lectures. It employs a modular, actor-based architecture using a custom GraphFlow execution engine for reliable, resumable processing.

---

## High-Level Data Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                     Video Agent Pipeline                        │
└─────────────────────────────────────────────────────────────────┘

1. INPUT
   └─> PDF/Markdown document
   
2. INGEST NODE
   └─> Parse document, extract text/metadata
   
3. SEGMENT NODE
   └─> Extract chapters using heuristics
       ├─ H1/H2 headers
       ├─ "Chapter N" patterns
       └─ Fallback: Size-based chunking
   
4. SCRIPT GENERATION NODE (Parallelizable)
   └─> For each chapter:
       ├─ LLM: Generate slide plan (with retry/validation)
       ├─ TTS: Synthesize audio for speaker notes
       ├─ Image: Generate images for slides
       └─ Checkpoint: Save per-chapter progress
   
5. VIDEO COMPOSITION NODE (Parallelizable)
   └─> For each chapter:
       ├─ Load images + audio
       ├─ Create SRT/VTT subtitles
       └─ Compose video (MP4)
   
6. MERGE NODE
   └─> Combine all chapter videos into final course video
   
7. OUTPUT
   └─> Per-chapter MP4 files + merged final video
```

---

## Core Components

### 1. **GraphFlow Engine** (`agent/GraphFlow/`)
Custom DAG (Directed Acyclic Graph) execution engine designed for reliable, resumable workflows.

**Key Features**:
- State-based execution with automatic merging
- Conditional routing and branching
- Thread-safe parallel execution
- Per-node error handling

**Files**:
- `graphflow.py` (417 lines) - StateGraph definition and compilation
- `engine.py` (446 lines) - Graph execution and state management
- `llm_utils.py` (285 lines) - LLM integration utilities

### 2. **Pipeline Execution** (`agent/graphflow_nodes.py`)
Defines the five pipeline stages as graph nodes.

**Stages**:
- **Ingest**: Read and parse input document
- **Segment**: Extract chapters from document
- **Script Generation**: Generate LLM-based slide scripts
- **Composition**: Create per-chapter videos
- **Merge**: Combine videos into final output

### 3. **Adapter System** (`agent/adapters/`)
Pluggable provider system for LLM, TTS, and image generation.

**Pattern**:
```
┌─────────────────────────────┐
│   Adapter Base Class        │
│  (Abstract Interface)       │
└──────────────┬──────────────┘
               │
      ┌────────┴────────┐
      │                 │
   Provider 1      Provider 2
  (OpenAI)        (Vertex AI)
  (ElevenLabs)    (Google TTS)
  (Stability)     (Replicate)
```

**Supported Providers**:
- **LLM**: OpenAI (GPT-4, GPT-3.5), Vertex AI (Gemini)
- **TTS**: Google Cloud TTS, ElevenLabs
- **Image**: Stability.ai, Replicate
- **Fallback**: Dummy implementations for testing

### 4. **Checkpoint & Resume** (`agent/runs_checkpoint.py`)
Enables interrupt-safe execution with per-chapter checkpointing.

**Features**:
- Per-chapter status tracking (pending, in_progress, completed, failed)
- Thread-safe checkpoint saves
- Automatic resume from last checkpoint
- Attempt archival to storage

### 5. **Caching System** (`agent/cache.py`)
Content-based artifact caching for improved performance.

**Benefits**:
- 60%+ speedup potential with 80% hit rate
- Applies to TTS audio, generated images, and videos
- Hash-based key generation for consistency

### 6. **Storage Backends** (`agent/storage/`)
Pluggable storage for artifact persistence.

**Supported**:
- Local filesystem (default)
- Google Cloud Storage (GCS)
- MinIO / S3-compatible storage

---

## Request/Response Flow

### Script Generation Flow

```
User Input (chapter text)
    ↓
[LLMClient.generate_and_validate()]
    ├─> Build prompt from template
    ├─> Call LLM adapter
    ├─> Validate response against schema
    ├─ If invalid: Retry with repair prompt (max 3x)
    ├─ If all fail: Use fallback DummyLLMAdapter
    └─> Return validated plan
    ↓
[ScriptGenerator.generate_slides_for_chapter()]
    ├─> For each slide in plan:
    │   ├─ Check cache for audio/image
    │   ├─ If missing:
    │   │   ├─ Call TTS adapter (if enabled)
    │   │   ├─ Call Image adapter (if enabled)
    │   │   └─ Save to cache
    │   └─ Attach URLs to slide
    ├─> Optional: Parallel execution (max N workers)
    └─> Return enriched slides
    ↓
Output (slides with audio/image URLs)
```

### Video Composition Flow

```
Slides (with audio/image URLs)
    ↓
[VideoComposer.compose_chapter()]
    ├─> Load audio files
    ├─> Load image files
    ├─> Generate subtitle tracks (SRT/VTT)
    ├─> Create video timeline
    │   ├─ Image duration from audio length
    │   ├─ Sync audio to image
    │   └─ Add subtitles
    ├─> Write MP4 file
    └─> Upload to storage (if configured)
    ↓
Output (MP4 video file)
```

---

## Parallel Execution Model

### Chapter-Level Parallelism

```
Chapters: [Ch1, Ch2, Ch3, Ch4]

Sequential (1 worker):
├─> Ch1: ████ (10s)
├─> Ch2: ████ (10s)
├─> Ch3: ████ (10s)
└─> Ch4: ████ (10s)
Total: 40s

Parallel (4 workers):
├─> Ch1: ████ (10s) ─┐
├─> Ch2: ████ (10s) ─┼─ Total: 10s
├─> Ch3: ████ (10s) ─┤
└─> Ch4: ████ (10s) ─┘
```

**Configuration**: `MAX_WORKERS` environment variable

### Slide-Level Parallelism

Within each chapter, slides can be processed in parallel for image/audio generation:

```
Slides: [S1, S2, S3, S4]

MAX_SLIDE_WORKERS: Controls parallel image/audio generation
SLIDE_RATE_LIMIT: Rate limiting for API calls (calls/sec)
```

---

## State Management

### Graph State Structure

```python
{
    # Input
    "input_path": str,           # Path to source document
    "run_id": str,               # Unique run identifier
    
    # Processing
    "file_content": {            # Parsed document
        "type": "markdown|pdf",
        "text": str,
        "pages": [...]
    },
    "chapters": [{               # Extracted chapters
        "id": str,
        "title": str,
        "text": str
    }],
    
    # Output
    "script_gen": [{             # Generated scripts per chapter
        "chapter_id": str,
        "slides": [...]
    }],
    "videos": [{                 # Composed videos
        "chapter_id": str,
        "video_url": str
    }],
    
    # Metadata
    "metadata": {},              # Arbitrary metadata
    "processing_log": [],        # Processing events
    "errors": []                 # Error messages
}
```

### State Reducers

When chapters are processed in parallel, results are merged using reducers:

```python
state_reducers = {
    "chapters": "extend",        # Append chapter results
    "script_gen": "extend",      # Append generated scripts
    "videos": "extend",          # Append videos
    "metadata": "merge",         # Merge metadata dicts
    "errors": "extend"           # Collect all errors
}
```

---

## Error Handling Strategy

### Multi-Level Fallbacks

```
1. Provider Implementation (e.g., OpenAI)
   └─> If error: Retry with exponential backoff
   
2. Adapter Layer (e.g., LLMAdapter)
   └─> If error: Try fallback provider
   
3. Factory Level
   └─> If error: Use Dummy adapter
   
4. Application Level
   └─> If error: Log and continue with fallback data
```

### LLM Validation & Repair

```
Generate → Parse JSON → Validate Schema
                │
            ❌ Invalid
                │
        Repair prompt (retry)
                │
            ❌ Still invalid (after 3 retries)
                │
        Use DummyLLMAdapter fallback
```

---

## Performance Characteristics

### Caching Impact

With content-based caching:
- **First run**: Full processing time
- **Subsequent runs**: 60-80% reduction (with 80% hit rate)
- **Hit key**: Hash of (chapter_text, model, provider)

### Parallel Scaling

```
1 worker:  100% baseline
2 workers: ~180% improvement (parallel overhead)
4 workers: ~320% improvement
8 workers: ~600% improvement (with rate limiting)
```

**Note**: Improvements depend on API rate limits and local hardware.

---

## Security Considerations

### API Key Management

- All API keys via environment variables (never hardcoded)
- Support for Google Application Credentials
- Per-provider authentication

### Data Handling

- Temporary files cleaned up after processing
- Optional: Archive LLM attempts to storage
- Optional: Clean local files after upload

### Thread Safety

- Lock-based synchronization for checkpoint files
- Thread-safe rate limiters
- Atomic file writes

---

## Deployment Models

### Model 1: Local Development
```
Local input → Python CLI → Local output
```

### Model 2: Cloud Processing
```
GCS input → Cloud Function/VM → GCS output
```

### Model 3: Batch Pipeline
```
Queue of documents → Worker pool → Storage backend
```

---

## Design Patterns Used

| Pattern | Location | Purpose |
|---------|----------|---------|
| **Adapter** | `adapters/` | Plugin provider system |
| **Factory** | `adapters/factory.py` | Create adapters by name |
| **State** | `graphflow_graph.py` | Graph state management |
| **Checkpoint** | `runs_checkpoint.py` | Resumable execution |
| **Cache** | `cache.py` | Avoid recomputation |
| **Rate Limiter** | `parallel.py` | API quota management |

---

## Next Steps

- Read **Chapter 2: Quick Start** for installation and basic usage
- Read **Chapter 3: Component Guide** for detailed module documentation
- Read **Chapter 4: Deployment** for production setup
- Read **Chapter 5: Testing** for test strategies
