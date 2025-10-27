# Troubleshooting Guide

This guide covers common issues encountered when using the video-agent system.

## Table of Contents
- [Installation Issues](#installation-issues)
- [API and Authentication Issues](#api-and-authentication-issues)
- [Video Composition Issues](#video-composition-issues)
- [Performance and Quota Issues](#performance-and-quota-issues)
- [Windows-Specific Issues](#windows-specific-issues)

---

## Installation Issues

### MoviePy Backend Compatibility (Windows)

**Symptoms**:
- `Could not find a backend to open image with iomode 'ri'`
- `'av.format.ContainerFormat' object has no attribute 'variable_fps'`
- `av.error.InvalidDataError: Invalid data found when processing input`

**Root Cause**: PyAV 13.0+ has breaking changes incompatible with moviepy 2.x

**Solution**: Use PyAV 12.3.0 (tested and stable):
```bash
pip install --user --force-reinstall "av==12.3.0"
```

**Verification**:
```bash
python -c "import av; print(f'PyAV version: {av.__version__}')"
# Should output: PyAV version: 12.3.0
```

**Alternative**: Use different backend if PyAV doesn't work:
```bash
pip install imageio[opencv]  # Option 1: OpenCV
pip install imageio[ffmpeg]  # Option 2: FFmpeg
```

---

## API and Authentication Issues

### Google API Key Not Found

**Symptoms**:
```
ValueError: Google API key not found. Set GOOGLE_API_KEY or GOOGLE_GENAI_API_KEY environment variable.
```

**Solution**: Create `.env` file in project root:
```bash
# Create .env from template
cp .env .env.local

# Add your API key
echo "GOOGLE_API_KEY=your_api_key_here" > .env
```

**Verification**:
```bash
python -c "from dotenv import load_dotenv; import os; load_dotenv(); print('✅ API Key Found' if os.getenv('GOOGLE_API_KEY') else '❌ API Key Missing')"
```

### 429 RESOURCE_EXHAUSTED - Quota Exceeded

**Symptoms**:
```
429 RESOURCE_EXHAUSTED. You exceeded your current quota
Quota exceeded for metric: predict_requests_per_model_per_day_paid_tier_1, limit: 70
```

**Root Cause**: Hit daily API quota limits

**Google API Free Tier Limits** (2025):
| Service | Daily Limit | Notes |
|---------|-------------|-------|
| Gemini 2.5 Flash (LLM) | 1,500 requests | Most generous |
| Imagen 4.0 Fast (Images) | 70 requests | **Most limiting** ⚠️ |
| Gemini TTS (Audio) | Varies | Usage-based |

**Solutions**:

1. **Wait for Reset**: Quotas reset at midnight Pacific Time

2. **Check Usage**: https://ai.dev/usage?tab=rate-limit

3. **Use Caching** (automatically enabled):
   ```bash
   # Verify cache is working
   ls -lh workspace/cache/*.meta.json | wc -l
   # Shows number of cached items
   ```

4. **Resume Interrupted Runs** (skip completed work):
   ```bash
   # Get run ID
   cat workspace/out/sample_lecture_results.json | grep '"run_id"'
   
   # Resume
   python -m agent.cli input.md --resume YOUR_RUN_ID --full-pipeline --out workspace/out
   ```

5. **Reduce Parallelization**:
   ```bash
   # Process slides sequentially (slower but respects rate limits)
   python -m agent.cli input.md --full-pipeline --max-slide-workers 1
   ```

6. **Upgrade Quota**: Visit [Google AI Studio Billing](https://aistudio.google.com)

---

## Video Composition Issues

### Base64-Encoded PNG Images (Legacy Issue)

**Symptoms**:
- PNG files exist but can't be opened in image viewers
- MoviePy error: `Invalid data found when processing input`
- File starts with text `iVBORw0KGgo...` instead of binary data

**Root Cause**: Older versions saved Imagen API responses as Base64 text instead of binary

**Check if Affected**:
```powershell
# Windows PowerShell
$file = "workspace/out/llm_logs/your_file.png"
$firstLine = Get-Content $file -TotalCount 1
if ($firstLine -match "^iVBOR") { 
    Write-Host "❌ Base64 text (needs conversion)" 
} else { 
    Write-Host "✅ Binary PNG (OK)" 
}
```

```bash
# Linux/Mac
head -c 20 workspace/out/llm_logs/your_file.png | file -
# Should show: PNG image data (binary)
# If shows: ASCII text (Base64), needs conversion
```

**Solution 1**: Update code and regenerate (recommended):
```bash
git pull origin main
rm workspace/out/llm_logs/*.png  # Delete old images
python -m agent.cli input.md --full-pipeline --out workspace/out
```

**Solution 2**: Manual conversion (if quota exhausted):
```powershell
# Windows PowerShell
Get-ChildItem workspace\out\llm_logs -Filter "*.png" | ForEach-Object {
    $content = Get-Content $_.FullName -Raw
    if ($content -match "^iVBOR") {
        $bytes = [System.Convert]::FromBase64String($content)
        [System.IO.File]::WriteAllBytes($_.FullName, $bytes)
        Write-Host "✅ Decoded: $($_.Name)"
    } else {
        Write-Host "⏭️  Skipped (already binary): $($_.Name)"
    }
}
```

```bash
# Linux/Mac
for file in workspace/out/llm_logs/*.png; do
    if head -c 10 "$file" | grep -q "^iVBOR"; then
        base64 -d "$file" > "${file}.tmp"
        mv "${file}.tmp" "$file"
        echo "✅ Decoded: $(basename $file)"
    fi
done
```

### Missing Audio Files

**Symptoms**:
- Video composition fails with `No such file` error for `.wav` files
- TTS generation silently fails

**Root Cause**: Gemini TTS API errors or missing audio generation

**Diagnosis**:
```bash
# Check if audio files exist
ls -lh workspace/out/llm_logs/*.wav

# Check run logs for TTS errors
grep -i "tts\|audio\|synthesize" workspace/out/llm_logs/*.log
```

**Solution**:
1. Verify Gemini TTS is working:
   ```bash
   python -c "from agent.google.services import GoogleServices; gs = GoogleServices(); gs.synthesize_speech('Test', 'test.wav'); print('✅ TTS works')"
   ```

2. Check API key has TTS permissions

3. Re-run with `--resume` to regenerate only missing audio

---

## Performance and Quota Issues

### Slow Generation (Many API Calls)

**Symptoms**: Pipeline takes very long, making many sequential API calls

**Solution**: Enable parallelization:
```bash
# Parallel chapter processing (4 workers)
python -m agent.cli input.md --full-pipeline --max-workers 4 --out workspace/out

# Parallel slide generation within chapters (2 workers)
python -m agent.cli input.md --full-pipeline --max-slide-workers 2
```

**Caution**: More parallelism = faster quota consumption. Monitor usage:
```bash
# Check cache to see what's already generated (won't regenerate)
ls workspace/cache/*.meta.json | wc -l
```

### Cache Not Working

**Symptoms**: Regenerating same content repeatedly despite cache enabled

**Diagnosis**:
```bash
# Check if cache is enabled
python -c "import os; print('Cache enabled:', os.getenv('CACHE_ENABLED', 'true'))"

# Check cache directory
ls -lh workspace/cache/
```

**Solution**:
```bash
# Ensure CACHE_ENABLED is not set to false
unset CACHE_ENABLED

# Or explicitly enable in .env
echo "CACHE_ENABLED=true" >> .env
```

---

## Windows-Specific Issues

### Duplicated Path (D:\D:\path\...)

**Symptoms**:
```
No such file: 'D:\D:\code-dive\video-agent\workspace\...'
```

**Root Cause**: Windows `file:///D:/` URL handling bug (fixed in latest version)

**Solution**: Update to latest code:
```bash
git pull origin main
```

The fix properly strips `file:///` prefix and handles Windows drive letters.

### PowerShell Environment Variables

**Symptoms**: Environment variables not persisting across terminal sessions

**Solution**: Use `.env` file instead of `$env:` commands:
```powershell
# ❌ Don't do this (session-only):
$env:GOOGLE_API_KEY = "your_key"

# ✅ Do this (persistent):
echo "GOOGLE_API_KEY=your_key" > .env
```

### Unicode/Encoding Errors

**Symptoms**: Errors with special characters in filenames or content

**Solution**: Ensure PowerShell uses UTF-8:
```powershell
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8
```

---

## Manual Video Composition

If you need to compose videos from existing assets without triggering API calls (useful when quota is exhausted), use the test script:

### Using compose_existing.py

**Location**: `tests/compose_existing.py`

**Purpose**: Compose videos from existing JSON results without regenerating missing assets

**Usage**:
```bash
# Compose videos from cached images/audio
python tests/compose_existing.py
```

**What it does**:
1. Loads `workspace/out/sample_lecture_results.json`
2. Checks if all required image and audio files exist
3. Skips chapters with missing files (no API calls)
4. Composes MP4 videos only for complete chapters
5. Saves videos to `workspace/out/{run_id}_chapter-XX.mp4`

**Output example**:
```
Loading results from: workspace\out\sample_lecture_results.json
Run ID: 10236a1c-4cf0-4ec0-84d2-604e45fe05ac
Total chapters: 6
🎬 Composing chapter-01 (1 slides)...
✅ Created: workspace/out/10236a1c_chapter-01.mp4
❌ Skipping chapter-05: Missing files
...
Videos created: 4
```

**When to use**:
- ✅ Quota exhausted but have some complete slides
- ✅ Testing video composition without API calls
- ✅ Want to see partial results before regenerating missing content

**Customization**:
Edit the script to change results file location:
```python
# Line 14
results_file = Path("workspace/out/your_results.json")
```

---

## Debugging Tips

### Enable Debug Logging

```bash
# Set environment variable for verbose output
export LOG_LEVEL=DEBUG

# Or in Python
python -c "import logging; logging.basicConfig(level=logging.DEBUG)"
```

### Check File Integrity

```bash
# Verify PNG files are valid
file workspace/out/llm_logs/*.png | grep -v "PNG image data"

# Check WAV audio files
file workspace/out/llm_logs/*.wav | grep -v "WAVE audio"

# Verify file sizes (should be > 100KB for images)
find workspace/out/llm_logs -name "*.png" -size -100k
```

### Test Individual Components

```python
# Test LLM
from agent.google.services import GoogleServices
gs = GoogleServices()
text = gs.generate_text("Hello, test")
print(f"✅ LLM works: {text[:50]}")

# Test TTS
gs.synthesize_speech("Test audio", "test.wav")
print("✅ TTS works: test.wav created")

# Test Image Generation
gs.generate_image("A test image", "test.png", width=1024, height=768)
print("✅ Image generation works: test.png created")
```

---

## Getting Additional Help

If you encounter issues not covered here:

1. **Check existing issues**: https://github.com/zhwa/video-agent/issues
2. **Search discussions**: https://github.com/zhwa/video-agent/discussions
3. **Create new issue**: Include:
   - Error message (full traceback)
   - OS and Python version
   - `pip list` output for installed packages
   - Steps to reproduce

**Useful diagnostic info to include**:
```bash
# System info
python --version
pip list | grep -E "(moviepy|av|imageio|google-genai)"

# Check installed backend
python -c "import imageio; print(imageio.config.plugins)"

# Environment check
python -c "from dotenv import load_dotenv; import os; load_dotenv(); print('GOOGLE_API_KEY:', '✅ Set' if os.getenv('GOOGLE_API_KEY') else '❌ Missing')"
```
