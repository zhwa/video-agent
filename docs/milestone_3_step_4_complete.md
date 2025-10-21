````markdown
# Milestone 3, Step 4: Pipeline Integration - COMPLETE ✅

**Date**: 2025-10-21
**Status**: ✅ COMPLETE

## Overview

Step 4 of Milestone 3 integrated TTS and image generation into the script
generation pipeline. Slides now include per-slide audio and images with
storage upload support. Slide-level asset generation supports controlled
concurrency via environment variables and CLI flags.

## Highlights

- Per-slide audio generation via TTS adapters (Google/ElevenLabs/Dummy).
- Per-slide image generation via Stability/Replicate/Dummy adapters.
- Assets are optionally uploaded to configured storage adapters (GCS/MinIO/Dummy).
- Per-slide generation can be parallelized with `MAX_SLIDE_WORKERS` and rate-limited with `SLIDE_RATE_LIMIT`.
- CLI supports `--max-slide-workers` and `--slide-rate` to configure parallelism.

## How to use

1. Configure providers via env vars (example uses dummy adapters for local runs):

```bash
export TTS_PROVIDER=dummy
export IMAGE_PROVIDER=dummy
export STORAGE_PROVIDER=dummy
export LLM_OUT_DIR=workspace/out
```

2. Run the CLI with slide-level parallelism:

```bash
python -m agent.cli sample.md --max-slide-workers 4 --slide-rate 2.0
```

## Tests added

- `tests/test_pipeline_image_tts.py` — verifies audio/image URLs are present per slide using dummy adapters.
- `tests/test_script_generator_parallel.py` — checks per-slide concurrency honors `MAX_SLIDE_WORKERS`.
- `tests/test_end_to_end_pipeline.py` — end-to-end run with dummy providers.

## Next steps

1. Add video composition to convert slides + assets into chapter MP4s (Milestone 4).
2. Improve caching and artifact deduping at the pipeline level.

````