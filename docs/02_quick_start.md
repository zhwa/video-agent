# Chapter 2: Quick Start Guide

## Installation

### Prerequisites

- **Python**: 3.9 or higher
- **pip**: Package installer
- **Virtual Environment**: Recommended (venv, conda, etc.)

### Step 1: Clone Repository

```bash
git clone https://github.com/zhwa/video-agent.git
cd video-agent
```

### Step 2: Create Virtual Environment

**Using venv**:
```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .\.venv\Scripts\Activate.ps1
```

**Using conda**:
```bash
conda create -n video-agent python=3.9
conda activate video-agent
```

### Step 3: Install Dependencies

```bash
pip install -r requirements.txt
```

**Main dependencies**:
- `langchain` - LLM orchestration
- `pydantic` - Data validation
- `pyyaml` - Configuration
- `pytest` - Testing
- `google-cloud-texttospeech` - TTS (optional)
- `openai` - OpenAI API (optional)
- `elevenlabs` - ElevenLabs API (optional)
- `moviepy` - Video composition (optional, for full pipeline)

---

## Basic Usage

### Example 1: Dummy Pipeline (No API Keys Needed)

```bash
python -m agent.cli examples/sample_lecture.md --full-pipeline --out workspace/out
```

**What happens**:
1. Reads `examples/sample_lecture.md`
2. Segments into chapters
3. Generates slide plans (using DummyLLMAdapter)
4. Creates dummy audio and images
5. Composes videos
6. Outputs to `workspace/out/`

**Duration**: ~30-60 seconds

### Example 2: With OpenAI Provider

```bash
# Set up environment
export LLM_PROVIDER=openai
export OPENAI_API_KEY=sk-...

# Run pipeline
python -m agent.cli examples/sample_lecture.md --full-pipeline --out workspace/out
```

### Example 3: With Vertex AI

```bash
# Set up environment
export LLM_PROVIDER=vertex
export GOOGLE_APPLICATION_CREDENTIALS=/path/to/credentials.json

# Run pipeline
python -m agent.cli examples/sample_lecture.md --full-pipeline --out workspace/out
```

### Example 4: Resume Interrupted Run

```bash
# If run was interrupted, get the run_id from workspace/runs/
python -m agent.cli examples/sample_lecture.md --full-pipeline --out workspace/out --resume RUN_ID
```

---

## Command-Line Options

### Basic Options

```bash
python -m agent.cli INPUT_FILE [OPTIONS]
```

**Positional Arguments**:
- `INPUT_FILE` - Path to PDF or Markdown file

**Essential Options**:
```bash
--full-pipeline              # Run complete pipeline (recommended)
--out DIR                   # Output directory (default: workspace/out)
--provider PROVIDER         # LLM provider: vertex|openai (default: vertex)
```

### Pipeline Control

```bash
--compose                   # Compose per-chapter videos
--merge                     # Merge all videos into one
--resume RUN_ID            # Resume from checkpoint
```

### Performance Options

```bash
--max-workers N            # Parallel chapter workers (default: 1)
--max-slide-workers N      # Parallel slide processing (default: 1)
--slide-rate-limit RATE    # Slide API calls/second
--compose-workers N        # Parallel video composition
--compose-rate RATE        # Composition calls/second
```

### Configuration Options

```bash
--llm-retries N            # LLM retry attempts (default: 3)
--llm-out DIR              # LLM attempt logs directory
--transition SECONDS       # Video transition duration (default: 0.0)
```

### Run Management

```bash
--list-runs                # List all saved runs
--inspect RUN_ID           # Show run metadata
```

---

## Environment Variables

### LLM Configuration

```bash
# Which LLM provider to use
LLM_PROVIDER=vertex|openai|dummy
LLM_MAX_RETRIES=3

# For OpenAI
OPENAI_API_KEY=sk-...

# For Vertex AI
GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json
GOOGLE_PROJECT_ID=your-project-id
```

### TTS Configuration

```bash
TTS_PROVIDER=google|elevenlabs|dummy
ELEVENLABS_API_KEY=...
```

### Image Configuration

```bash
IMAGE_PROVIDER=stability|replicate|dummy
STABILITY_API_KEY=...
REPLICATE_API_TOKEN=...
```

### Storage Configuration

```bash
STORAGE_PROVIDER=gcs|minio|none

# For GCS
GCS_BUCKET=your-bucket
GCS_PROJECT_ID=your-project

# For MinIO
MINIO_ENDPOINT=minio.example.com:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
```

### Processing Configuration

```bash
MAX_WORKERS=4                      # Parallel chapters
MAX_SLIDE_WORKERS=2                # Parallel slides
SLIDE_RATE_LIMIT=10                # API calls/second
CACHE_ENABLED=true                 # Enable caching
CACHE_DIR=workspace/cache
RUNS_DIR=workspace/runs
```

---

## Configuration Files

### YAML Configuration (Optional)

Create `config/providers.yaml`:

```yaml
llm:
  provider: vertex
  max_retries: 3
  timeout: 30

tts:
  provider: google
  
image:
  provider: stability
  
storage:
  provider: gcs
  bucket: my-bucket

processing:
  max_workers: 4
  max_slide_workers: 2
  cache_enabled: true
```

Then run:
```bash
python -m agent.cli input.md --config config/providers.yaml --full-pipeline
```

---

## Common Workflows

### Workflow 1: Development (Dummy Providers)

```bash
# No credentials needed, fast iteration
python -m agent.cli lesson.md --full-pipeline --out output/
```

### Workflow 2: Production (Real Providers)

```bash
# Set up environment
export LLM_PROVIDER=openai
export OPENAI_API_KEY=sk-...
export TTS_PROVIDER=google
export IMAGE_PROVIDER=stability

# Run pipeline
python -m agent.cli lesson.md --full-pipeline --out output/ --max-workers 4
```

### Workflow 3: Large-Scale Processing

```bash
# Process multiple files with parallel chapter processing
export MAX_WORKERS=8
export STORAGE_PROVIDER=gcs
export GCS_BUCKET=my-bucket

for file in lectures/*.md; do
    python -m agent.cli "$file" --full-pipeline --out workspace/out/
done
```

### Workflow 4: Resume After Interruption

```bash
# Run was interrupted at run_id_abc123
python -m agent.cli lesson.md --full-pipeline --out output/ --resume run_id_abc123
```

---

## Troubleshooting

### Issue: "ImportError: No module named 'moviepy'"

**Solution**: Install moviepy for video composition
```bash
pip install moviepy
```

**Workaround**: Process up to script generation without composition
```bash
python -m agent.cli input.md --out output/  # Skip --full-pipeline
```

### Issue: "OpenAI API key not found"

**Solution**: Set environment variable
```bash
export OPENAI_API_KEY=sk-...
python -m agent.cli input.md --provider openai --full-pipeline --out output/
```

### Issue: "No chapters detected in document"

**Solution**: Ensure document has proper structure:
- Markdown: Use `# Chapter Title` headers
- PDF: Include chapter markers

Example Markdown:
```markdown
# Chapter 1: Introduction

Content here...

# Chapter 2: Main Topic

Content here...
```

### Issue: "Rate limit exceeded"

**Solution**: Add rate limiting
```bash
export SLIDE_RATE_LIMIT=5  # Max 5 calls/second
python -m agent.cli input.md --full-pipeline --max-slide-workers 1 --out output/
```

### Issue: "Vertex AI credentials not found"

**Solution**: Set up authentication
```bash
gcloud auth application-default login
python -m agent.cli input.md --provider vertex --full-pipeline --out output/
```

---

## Output Structure

After running the pipeline, outputs are organized as:

```
workspace/
├── out/                          # Results
│   ├── sample_lecture_results.json
│   ├── videos/
│   │   ├── chapter_01.mp4
│   │   ├── chapter_02.mp4
│   │   └── final_output.mp4
│   └── llm_logs/               # LLM attempts (if enabled)
│       ├── attempt_01_prompt.txt
│       └── attempt_01_response.txt
│
├── runs/                         # Checkpoints
│   └── run_id_abc123/
│       ├── metadata.json
│       ├── checkpoint.json
│       └── script_gen_chapters/
│
└── cache/                        # Cached artifacts
    ├── abc123def456.mp3
    ├── abc123def456.meta.json
    └── ...
```

---

## Next Steps

1. **Run the dummy pipeline**: `python -m agent.cli examples/sample_lecture.md --full-pipeline --out workspace/out`
2. **Check the output**: Look in `workspace/out/` for results
3. **Set up real providers**: Add API keys and run with `--provider openai` or similar
4. **Read Component Guide**: See Chapter 3 for detailed component documentation
5. **Configure for production**: See Chapter 4 for deployment guidance

---

## Getting Help

**Common Questions**:
- How do I add a new provider? See Chapter 3: Component Guide
- How do I deploy this in production? See Chapter 4: Deployment
- How do I run tests? See Chapter 5: Testing

**Documentation**:
- Architecture details: [Chapter 1: Architecture Overview](01_architecture_overview.md)
- Component reference: [Chapter 3: Component Guide](03_component_guide.md)
- Deployment guide: [Chapter 4: Deployment](04_deployment.md)
- Testing: [Chapter 5: Testing](05_testing.md)
