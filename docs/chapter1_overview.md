# Chapter 1 — Overview

This repository contains a small, plug-in based pipeline that converts lecture
content (PDF or Markdown) into scripted slides, synthesized audio, and final
video lectures. The project is designed to be modular and testable with
simple dummy adapters for offline or CI runs.

## Key Features

- **File ingestion** for Markdown and PDF
- **Chapter segmentation** and structured slide generation
- **TTS and image generation** per slide (pluggable adapters)
- **Per-chapter video composition** and final merge (MoviePy/FFmpeg)
- **Artifact persistence and upload** via storage adapters (GCS/MinIO/Dummy)
- **Caching** with content hash keys
- **Telemetry, checkpointing, and resume** support

## Educational Goals

- Provide a minimal but complete end-to-end flow from content to video
- Keep components small and individually testable
- Allow easy substitution of provider adapters
- Demonstrate production-quality patterns in real code

## Repository Structure

```
agent/                 # Core modules (35+ files)
├── adapters/         # LLM, TTS, image, storage, embeddings
├── storage/          # GCS, MinIO, dummy storage
├── cache.py          # Content-based caching
├── llm_client.py     # LLM integration with retry
├── script_generator.py # Slide generation
├── video_composer.py # Video assembly
├── cli.py            # Command-line interface
├── langgraph_nodes.py # Pipeline orchestration
└── runs_safe.py      # Thread-safe checkpointing

tests/                # 76+ comprehensive tests
docs/                 # Documentation (11 chapters + appendices)
```

## Learning Path: 11-Chapter Progression

### Core Understanding (Chapters 1-3)
- **Chapter 1**: Overview (this file)
- **Chapter 2**: Architecture & System Design
- **Chapter 2B**: Configuration & Environment Setup

### Implementation Details (Chapters 4-5)
- **Chapter 4**: Code Walkthrough: Implementation Details
- **Chapter 5**: Design Patterns: Solutions for Complex Problems

### Production Patterns (Chapters 6-8)
- **Chapter 6**: Error Handling & Logging
- **Chapter 7**: Concurrency & Threading
- **Chapter 8**: Testing Strategies

### Hands-On Learning (Chapters 9 + Appendices)
- **Chapter 9**: Getting Started: Hands-On Exercises
- **Chapter 3**: Key Concepts & Design Principles (reference)
- **Appendix A**: Caching & Performance Optimization
