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
- `python-dotenv` - Automatic .env file loading
- `moviepy` - Video composition (optional, for full pipeline)

**For video composition** (Windows users):
```bash
pip install moviepy
pip install "av==12.3.0"  # Compatible PyAV version
```

**Note**: If you encounter PyAV compatibility issues, see Troubleshooting section below.

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

**Step 1: Configure API Key (One-Time)**

Create a `.env` file in the project root:

```bash
# Copy the template
cp .env .env.local  # Keep .env as template, use .env.local for your key

# Edit .env with your API key
notepad .env  # Windows
# or
nano .env     # Linux/Mac
```

Add your API key:
```env
GOOGLE_API_KEY=your_actual_api_key_here
```

Get your API key from [Google AI Studio](https://aistudio.google.com/apikey).

**Step 2: Run Pipeline**

```bash
# No need to export - .env is loaded automatically!
python -m agent.cli examples/sample_lecture.md --full-pipeline --out workspace/out
```

**What happens**:
1. Uses Google Gemini for LLM slide generation
2. Uses Gemini 2.5 native TTS for audio synthesis (WAV format)
3. Uses Google Imagen 4.0 for image generation
4. Creates professional videos with all real content

**Why .env file?**
- ✅ Automatic loading on every run
- ✅ Persistent across terminal sessions
- ✅ Secure (never committed to git)
- ✅ Cross-platform (Windows, macOS, Linux)

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

Add to your `.env` file:

```env
# Required: Google API Key for Gemini, Imagen, and TTS
GOOGLE_API_KEY=your_api_key_here

# Optional: Override default models
GOOGLE_LLM_MODEL=gemini-2.5-flash
GOOGLE_IMAGE_MODEL=imagen-4.0-fast-generate-001

# Optional: Customize TTS voice (default: Puck)
GOOGLE_TTS_VOICE=Puck
# Available voices: Puck, Charon, Kore, Fenrir, Aoede, etc.
# See: https://ai.google.dev/gemini-api/docs/speech

# LLM Configuration
LLM_MAX_RETRIES=3
```

**Note**: `.env` file is automatically loaded by `python-dotenv`. No need for `export` commands!

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
# API key is loaded from .env automatically

# Run pipeline with parallelization
python -m agent.cli lesson.md --full-pipeline --out output/ --max-workers 4
```

### Workflow 3: Large-Scale Processing

```bash
# Add to .env:
# MAX_WORKERS=8
# GOOGLE_API_KEY=your-api-key-here

# Process multiple files with parallel chapter processing
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

**Solution**: Install moviepy and compatible image backend
```bash
pip install moviepy
pip install "av==12.3.0"  # Compatible PyAV version for Windows
```

**Note**: MoviePy requires an image backend. If you get errors like:
- `Could not find a backend to open image with iomode 'ri'`
- `'av.format.ContainerFormat' object has no attribute 'variable_fps'`

**Fix**: Use PyAV 12.3.0 (tested and compatible with moviepy 2.x):
```bash
# Windows users: Use specific PyAV version
pip install --user --force-reinstall "av==12.3.0"
```

**Alternative backends** (if PyAV doesn't work):
```bash
pip install imageio[opencv]  # OpenCV backend
pip install imageio[ffmpeg]  # FFmpeg backend
```

**Workaround**: Process up to script generation without composition
```bash
python -m agent.cli input.md --out output/  # Skip --full-pipeline
```

### Issue: "Google API key not found"

**Solution**: Create `.env` file with your API key

```bash
# Create .env file
echo "GOOGLE_API_KEY=your_api_key_here" > .env

# Or copy template and edit
cp .env .env.local
notepad .env  # Edit with your key
```

**Verify API key is loaded**:
```bash
python -c "from dotenv import load_dotenv; import os; load_dotenv(); print('API Key:', 'Found' if os.getenv('GOOGLE_API_KEY') else 'NOT FOUND')"
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

### Issue: "429 RESOURCE_EXHAUSTED" or "Quota exceeded"

**Problem**: You've hit your daily API quota limits

**Google API Free Tier Limits** (as of 2025):
- Gemini 2.5 Flash: 1,500 requests/day
- Imagen 4.0 Fast: 70 requests/day ⚠️ (most limiting)
- Gemini TTS: Varies by usage

**Solutions**:

1. **Wait for quota reset**: Quotas reset at midnight Pacific Time

2. **Use caching to avoid re-generation**:
   ```bash
   # Cache is enabled by default - already generated content won't be regenerated
   # Check cached files in workspace/cache/
   ls workspace/cache
   ```

3. **Resume from checkpoint** (if run was interrupted):
   ```bash
   # Get run ID from results
   cat workspace/out/sample_lecture_results.json | grep run_id
   
   # Resume from that run (skips already-generated slides)
   python -m agent.cli input.md --resume RUN_ID --full-pipeline --out workspace/out
   ```

4. **Reduce parallelization** (to stay under rate limits):
   ```bash
   # Process slides sequentially
   python -m agent.cli input.md --full-pipeline --max-slide-workers 1 --out workspace/out
   ```

5. **Upgrade quota**: Visit [Google AI Studio](https://aistudio.google.com) billing settings

**Check current usage**:
```bash
# Visit: https://ai.dev/usage?tab=rate-limit
# Or check error message for quota details
```

### Issue: "No such file: 'D:\D:\path\...'" (Duplicated path on Windows)

**Problem**: Windows file:// URL handling issue (fixed in latest version)

**Solution**: Update to latest code
```bash
git pull origin main
```

The fix handles Windows `file:///D:/` URLs correctly by stripping the extra leading slash.

### Issue: "Invalid data found when processing input" (PNG files)

**Problem**: PNG images are Base64-encoded text instead of binary (legacy issue, fixed)

**Quick check**:
```powershell
# Check if PNG is text or binary
$file = "workspace/out/llm_logs/your_file.png"
$content = Get-Content $file -TotalCount 1
if ($content -match "^iVBOR") { Write-Host "❌ Base64 text" } else { Write-Host "✅ Binary" }
```

**Solution**: Update code and regenerate images
```bash
git pull origin main
# Delete old Base64 images
rm workspace/out/llm_logs/*.png
# Regenerate
python -m agent.cli input.md --full-pipeline --out workspace/out
```

**Manual fix** (if you can't regenerate due to quota):
```powershell
# Convert Base64 PNGs to binary
Get-ChildItem workspace\out\llm_logs -Filter "*.png" | ForEach-Object {
    $content = Get-Content $_.FullName -Raw
    if ($content -match "^iVBOR") {
        $bytes = [System.Convert]::FromBase64String($content)
        [System.IO.File]::WriteAllBytes($_.FullName, $bytes)
        Write-Host "✅ Decoded: $($_.Name)"
    }
}
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
- Troubleshooting: [Chapter 6: Troubleshooting Guide](06_troubleshooting.md)
