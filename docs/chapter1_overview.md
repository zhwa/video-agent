# Chapter 1 — Overview

This repository contains a small, plug-in based pipeline that converts lecture
content (PDF or Markdown) into scripted slides, synthesized audio, and final
video lectures. The project is designed to be modular and testable with
simple dummy adapters for offline or CI runs.

Key features
- File ingestion for Markdown and PDF
- Chapter segmentation and structured slide generation
- TTS and image generation per slide (pluggable adapters)
- Per-chapter video composition and final merge (MoviePy/FFmpeg)
- Artifact persistence and upload via storage adapters (GCS/MinIO/Dummy)
- Basic telemetry, checkpointing, and resume support

Goals
- Provide a minimal but complete end-to-end flow from content to video.
- Keep components small and individually testable.
- Allow easy substitution of provider adapters.

Repository layout
- `agent/` — core modules (ingest, segmenter, script generation, adapters,
  video composer, storage, telemetry)
- `tests/` — unit/integration tests (use dummy providers where appropriate)
- `docs/` — high-level documentation and usage instructions
- `config/` — provider configuration example
