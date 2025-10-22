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
- `langgraph` - Workflow orchestration
- `pydantic` - Data validation
- `pyyaml` - Configuration
- `pytest` - Testing
- `google-genai` - Google Gemini & Imagen APIs
- `google-cloud-texttospeech` - Google Cloud TTS
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

### Example 2: With Google API Key

```bash
# Set up environment
export GOOGLE_API_KEY=your-api-key-here

# Run pipeline
python -m agent.cli examples/sample_lecture.md --full-pipeline --out workspace/out
```

**What happens**:
1. Uses Google Gemini for LLM slide generation
2. Uses Google Cloud TTS for audio synthesis
3. Uses Google Imagen 3.0 for image generation
4. Creates professional videos with all real content

### Example 3: Resume Interrupted Run

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

### Google API Configuration

```bash
# Google API Key (required for real content generation)
GOOGLE_API_KEY=your-api-key-here

# Optional: Google Cloud credentials for TTS
GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json

# LLM Configuration
LLM_MAX_RETRIES=3
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

Create `config/settings.yaml`:

```yaml
google:
  api_key: ${GOOGLE_API_KEY}  # Use environment variable
  max_retries: 3
  timeout: 30

processing:
  max_workers: 4
  max_slide_workers: 2
  cache_enabled: true
  cache_dir: workspace/cache
  
output:
  video_format: mp4
  transition_duration: 0.0
```

Then run:
```bash
python -m agent.cli input.md --config config/settings.yaml --full-pipeline
```

---

## Common Workflows

### Workflow 1: Development (Dummy Providers)

```bash
# No credentials needed, fast iteration
python -m agent.cli lesson.md --full-pipeline --out output/
```

### Workflow 2: Production (Google Services)

```bash
# Set up environment
export GOOGLE_API_KEY=your-api-key-here

# Run pipeline with parallelization
python -m agent.cli lesson.md --full-pipeline --out output/ --max-workers 4
```

### Workflow 3: Large-Scale Processing

```bash
# Process multiple files with parallel chapter processing
export MAX_WORKERS=8
export GOOGLE_API_KEY=your-api-key-here

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

### Issue: "Google API key not found"

**Solution**: Set environment variable
```bash
export GOOGLE_API_KEY=your-api-key-here
python -m agent.cli input.md --full-pipeline --out output/
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

### Issue: "Failed to generate content"

**Solution**: Verify API key is valid
```bash
# Test API key
python -c "import os; from agent.google import GoogleServices; gs = GoogleServices(); print('API key valid!')"

# Check API quotas in Google Cloud Console
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
3. **Set up Google API**: Get API key from Google AI Studio and set `GOOGLE_API_KEY`
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
