# Chapter 2B — Configuration & Environment Setup

This chapter explains how to configure the Video Agent for different scenarios and providers.

## Environment Variables Reference

### Core Configuration

```bash
# Output and logging
OUT_DIR="workspace/out"              # Where to write results
LLM_OUT_DIR="workspace/llm_logs"    # Where to store LLM attempt logs
RUNS_DIR="workspace/runs"            # Where to store run checkpoints
CACHE_DIR="workspace/cache"          # Where to cache generated files
CACHE_ENABLED="true"                 # Enable/disable caching

# Logging
LOG_LEVEL="INFO"                     # DEBUG, INFO, WARNING, ERROR

# Concurrency
MAX_WORKERS="4"                      # Max parallel chapter workers
MAX_SLIDE_WORKERS="2"                # Max parallel slide generation workers
MAX_COMPOSER_WORKERS="1"             # Max parallel video composition workers

# Rate Limiting (requests per second)
LLM_RATE_LIMIT="10"                  # LLM API calls/sec
SLIDE_RATE_LIMIT="5"                 # Slide asset generation calls/sec
COMPOSER_RATE_LIMIT="1"              # Video composition calls/sec
```

### LLM Provider Configuration

#### OpenAI
```bash
LLM_PROVIDER="openai"
OPENAI_API_KEY="sk-..."              # Your OpenAI API key
OPENAI_MODEL="gpt-4o-mini"           # Model to use
LLM_MAX_RETRIES="3"                  # Retry attempts on failure
```

#### Google Vertex AI
```bash
LLM_PROVIDER="vertex"
GOOGLE_APPLICATION_CREDENTIALS="/path/to/creds.json"  # Or use default application credentials
# OR
GOOGLE_API_KEY="..."                 # Direct API key

# Optional
GOOGLE_CLOUD_PROJECT="your-project"
GOOGLE_CLOUD_REGION="us-central1"
```

#### Fallback (Dummy - Always Available)
```bash
LLM_PROVIDER="dummy"                 # No configuration needed
```

### TTS Provider Configuration

#### Google Cloud Text-to-Speech
```bash
TTS_PROVIDER="google"
GOOGLE_APPLICATION_CREDENTIALS="/path/to/creds.json"
```

#### ElevenLabs
```bash
TTS_PROVIDER="elevenlabs"
ELEVENLABS_API_KEY="..."              # Your ElevenLabs API key
ELEVENLABS_VOICE_ID="21m00Tcm4TlvDq8ikWAM"  # Voice ID to use
```

#### Fallback (Dummy)
```bash
TTS_PROVIDER="dummy"                 # No configuration needed
```

### Image Generation Provider Configuration

#### Stability.ai (Stable Diffusion)
```bash
IMAGE_PROVIDER="stability"
STABILITY_API_KEY="sk-..."            # Your Stability API key
```

#### Replicate
```bash
IMAGE_PROVIDER="replicate"
REPLICATE_API_TOKEN="..."             # Your Replicate API token
```

#### Fallback (Dummy)
```bash
IMAGE_PROVIDER="dummy"               # No configuration needed
```

### Storage Provider Configuration

#### Google Cloud Storage (GCS)
```bash
STORAGE_PROVIDER="gcs"
GOOGLE_APPLICATION_CREDENTIALS="/path/to/creds.json"
GCS_BUCKET="your-bucket-name"
GCS_PROJECT_ID="your-project-id"
```

#### MinIO
```bash
STORAGE_PROVIDER="minio"
MINIO_ENDPOINT="minio.example.com:9000"
MINIO_ACCESS_KEY="minioadmin"
MINIO_SECRET_KEY="minioadmin"
MINIO_BUCKET="videos"
MINIO_USE_SSL="true"                 # Use HTTPS if "true"
```

#### Fallback (Dummy - Local Files Only)
```bash
STORAGE_PROVIDER="dummy"             # No configuration needed
```

---

## Configuration Patterns

### Pattern 1: Local Development (No APIs)

```bash
#!/bin/bash
# Use all dummy providers (no API keys needed)
export LLM_PROVIDER="dummy"
export TTS_PROVIDER="dummy"
export IMAGE_PROVIDER="dummy"
export STORAGE_PROVIDER="dummy"

# Run with full pipeline
python -m agent.cli input.md --full-pipeline --out workspace/out
```

**Use case**: Development, testing, CI/CD

### Pattern 2: OpenAI with Local Storage

```bash
#!/bin/bash
# Use OpenAI for LLM, other providers as dummy
export LLM_PROVIDER="openai"
export OPENAI_API_KEY="sk-..."
export TTS_PROVIDER="dummy"
export IMAGE_PROVIDER="dummy"
export STORAGE_PROVIDER="dummy"

# Run
python -m agent.cli input.md --full-pipeline --out workspace/out
```

**Use case**: Quick testing with real LLM but dummy media generation

### Pattern 3: Production (Google Cloud)

```bash
#!/bin/bash
# Use all Google Cloud providers
export LLM_PROVIDER="vertex"
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/creds.json"

export TTS_PROVIDER="google"
export IMAGE_PROVIDER="replicate"  # or stability
export REPLICATE_API_TOKEN="..."

export STORAGE_PROVIDER="gcs"
export GCS_BUCKET="video-output"
export GCS_PROJECT_ID="my-project"

# Configure concurrency for production
export MAX_WORKERS="8"
export MAX_SLIDE_WORKERS="4"
export LLM_RATE_LIMIT="50"

# Run
python -m agent.cli input.md --full-pipeline --out workspace/out
```

**Use case**: Production video generation

### Pattern 4: Hybrid (Multi-Provider)

```bash
#!/bin/bash
# Best-of-breed providers
export LLM_PROVIDER="openai"           # Best model
export OPENAI_API_KEY="sk-..."

export TTS_PROVIDER="elevenlabs"       # Best voice quality
export ELEVENLABS_API_KEY="..."

export IMAGE_PROVIDER="stability"      # Best images
export STABILITY_API_KEY="sk-..."

export STORAGE_PROVIDER="minio"        # Self-hosted storage
export MINIO_ENDPOINT="storage.local:9000"
export MINIO_ACCESS_KEY="minioadmin"
export MINIO_SECRET_KEY="minioadmin"

python -m agent.cli input.md --full-pipeline --out workspace/out
```

**Use case**: Optimal results using best provider for each component

---

## Configuration File (providers.yaml)

For more complex setups, use `config/providers.yaml`:

```yaml
llm:
  provider: "openai"
  openai:
    api_key: "${OPENAI_API_KEY}"
    model: "gpt-4o-mini"
  vertex:
    project_id: "${GOOGLE_CLOUD_PROJECT}"
    location: "us-central1"

tts:
  provider: "elevenlabs"
  google:
    credentials_path: "${GOOGLE_APPLICATION_CREDENTIALS}"
  elevenlabs:
    api_key: "${ELEVENLABS_API_KEY}"
    voice_id: "21m00Tcm4TlvDq8ikWAM"

image:
  provider: "stability"
  stability:
    api_key: "${STABILITY_API_KEY}"
  replicate:
    api_token: "${REPLICATE_API_TOKEN}"

storage:
  provider: "gcs"
  gcs:
    project_id: "${GCS_PROJECT_ID}"
    bucket: "${GCS_BUCKET}"
  minio:
    endpoint: "${MINIO_ENDPOINT}"
    access_key: "${MINIO_ACCESS_KEY}"
    secret_key: "${MINIO_SECRET_KEY}"
    bucket: "videos"
    use_ssl: true

concurrency:
  max_workers: 4
  max_slide_workers: 2
  max_composer_workers: 1
  llm_rate_limit: 10
  slide_rate_limit: 5
```

---

## Fallback Behavior

The Video Agent implements **graceful degradation** - if a provider is unavailable, it falls back to a dummy implementation:

```python
# If OpenAI fails to initialize
LLM_PROVIDER="openai" 
  → ImportError or API key missing
    → Falls back to Dummy LLM Adapter
      → Generates deterministic heuristic slides

# Similar for all providers:
# TTS, Image Generation, Storage, Embeddings
```

### How Fallback Works

```
get_llm_adapter("openai")
  ↓
  Try: from .openai_adapter import OpenAIAdapter
  ↓
  If success → return OpenAIAdapter()
  ↓
  If ImportError (openai not installed)
    → log.warning("OpenAI not installed, using dummy")
    → return DummyLLMAdapter()
  ↓
  If Exception (API key missing, network error)
    → log.warning("Failed to initialize OpenAI, using dummy")
    → return DummyLLMAdapter()
```

**Benefits**:
- Pipeline never completely fails
- Can develop/test without API keys
- Gracefully handles temporary outages
- Clear logging of what happened

---

## Configuration Validation

To check if your configuration is valid:

```bash
# 1. Check environment variables
python -c "import os; print({k:v for k,v in os.environ.items() if k.startswith(('LLM_', 'TTS_', 'IMAGE_', 'STORAGE_'))})"

# 2. Check adapter initialization
python -c "
from agent.adapters.factory import get_llm_adapter, get_tts_adapter, get_image_adapter
from agent.storage import get_storage_adapter

print('LLM:', get_llm_adapter().__class__.__name__)
print('TTS:', get_tts_adapter().__class__.__name__)
print('Image:', get_image_adapter().__class__.__name__)
print('Storage:', get_storage_adapter().__class__.__name__ if get_storage_adapter() else 'None')
"

# 3. List available runs
python -m agent.cli --list-runs
```

---

## Troubleshooting Configuration Issues

### Issue 1: "OpenAI not installed"
```
Error: ImportError: openai library is required for OpenAIAdapter but not installed

Solution:
  pip install openai
```

### Issue 2: "OpenAI API key not found"
```
Error: openai.error.AuthenticationError: Invalid API key

Solution:
  export OPENAI_API_KEY="sk-..."
```

### Issue 3: Vertex AI credentials not found
```
Warning: Vertex credentials not detected in environment

Solution:
  export GOOGLE_APPLICATION_CREDENTIALS="/path/to/creds.json"
  # or export GOOGLE_API_KEY="..."
```

### Issue 4: Storage adapter not initialized
```
Info: Using Dummy storage adapter

Solution:
  export STORAGE_PROVIDER="gcs" or "minio"
  Set required environment variables for chosen provider
```

### Issue 5: Rate limit too aggressive
```
Symptom: Requests are throttled/delayed excessively

Solution:
  Increase rate limits:
  export LLM_RATE_LIMIT="50"
  export SLIDE_RATE_LIMIT="20"
```

### Issue 6: Out of memory with parallel workers
```
Symptom: ProcessPoolExecutor runs out of memory

Solution:
  Reduce workers:
  export MAX_WORKERS="2"
  export MAX_SLIDE_WORKERS="1"
```

---

## CLI Arguments vs Environment Variables

CLI arguments **override** environment variables:

```bash
# These are equivalent:
export MAX_WORKERS=4
python -m agent.cli input.md

# Override with CLI:
python -m agent.cli input.md --max-workers 8  # Uses 8, not 4
```

**Priority order** (highest to lowest):
1. CLI arguments (`--max-workers 8`)
2. Environment variables (`MAX_WORKERS=4`)
3. Defaults in code (`max_workers=1`)

---

## Next Steps

- See [Chapter 4: Code Walkthrough](chapter4_code_walkthrough.md) to understand how configuration is used
- See [Chapter 3: Design Patterns](chapter3_key_concepts.md) to understand adapter factory pattern
- See [Chapter 1: Overview](chapter1_overview.md) for quick start examples

