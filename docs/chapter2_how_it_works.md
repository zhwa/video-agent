# Chapter 2 — How the Agent Works

This document explains the end-to-end pipeline and how LangGraph-style
orchestration maps to the code in this repository.

Pipeline overview
1. Ingest: read a Markdown or PDF file and normalize to a structured format.
2. Segment: split the content into chapters using heuristics (headers or
   default chunking).
3. Script generation: for each chapter, call an LLM adapter (with retries and
   validation) to produce a structured slide plan.
4. Asset generation: per slide, synthesize TTS audio and generate an image; the
   pipeline can run these concurrently and uploads artifacts to storage.
5. Composition: per-chapter video is composed from images and audio, then
   optionally merged into a full course video.
6. Persistence: intermediate results and artifacts are checkpointed to enable
   resuming runs and post-hoc inspection.

LangGraph mapping
The project uses a LangGraph-inspired description for the flow. The small
runtime is implemented in `agent/langgraph_nodes.py`. It exposes a
declarative graph description via `build_graph_description()` and runs the
steps sequentially in `run_graph_description()`.
