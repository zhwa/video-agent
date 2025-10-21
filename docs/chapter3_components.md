# Chapter 3 — Components and Implementation

This document describes each logical component and where it is implemented in
the repository.

- Ingest & IO (`agent/io.py`)
  - `read_file()` dispatches to `read_markdown()` or `read_pdf()`.
  - Markdown front-matter handling and optional title extraction.

- Segmenter (`agent/segmenter.py`)
  - Heuristic-based splitting using headers, chapter markers, or sentence
    chunking. The implementation is deterministic and unit tested.

- LLM client (`agent/llm_client.py`)
  - Centralizes retries, validation, and attempt logging.
  - Writes local attempt logs when `LLM_OUT_DIR` is configured.
  - Archives attempts to storage (via `get_storage_adapter`) optionally.

- Script generator (`agent/script_generator.py`)
  - Transforms chapter text into slide plans using the selected LLM adapter.
  - Optionally generates slide-level assets (TTS audio and images).
  - Uploads assets to storage and records their URLs in the slide data.

- Video composer (`agent/video_composer.py`)
  - Uses MoviePy to assemble images and audio into a single MP4 per chapter.
  - Generates SRT subtitles from slide speaker notes.
  - Caches outputs via `agent/cache.py` to avoid recomposition.

- Storage adapters (`agent/storage/*`)
  - Dummy, GCS and MinIO adapters with the same interface (`upload_file` and
    `download_file`). The factory `get_storage_adapter` returns the
    configured adapter.

- Adapters layer (`agent/adapters/*`)
  - LLM adapters (Vertex/OpenAI/Dummy), embeddings, TTS (Google/ElevenLabs
    stubs), image adapters, and vector DB implementations.

- Checkpoints and runs (`agent/runs.py`)
  - Maintains `workspace/runs/{run_id}/metadata.json` and `checkpoint.json`.
  - Exposes helpers to add artifacts and list runs.

- Telemetry (`agent/telemetry.py`)
  - Simple in-memory collector used for timings and counters across the
    pipeline. Instrumentation is placed in core hotspots.
