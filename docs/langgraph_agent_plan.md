# LangGraph: PDF/Markdown -> Video Lecture Agent — Refined Plan

Status: planning

This document refines the implementation plan for a LangGraph agent that:
- ingests PDFs and Markdown files (single files or directories),
- segments content into chapters,
- generates a structured lecture script for each chapter,
- produces voice (TTS) and visuals (images/video) per slide/chapter,
- assembles narrated lecture video files,
- persists artifacts and indexes text for retrieval.

The implementation targets Google Cloud as the default provider but is designed
so it can be switched to Chinese providers (Baidu, Alibaba, Tencent, iFLYTEK,
etc.) or to local/self-hosted alternatives if Google services are unavailable.

Requirements
- Inputs: single PDF, single Markdown, or directory containing .pdf/.md files
- Outputs: per-chapter video (.mp4), per-chapter audio (.mp3), captions (.srt),
  artifacts (images, prompts, transcripts), searchable index (vector DB)
- Configurable provider adapters (LLM, embeddings, OCR, TTS, image/video
  generation, storage, vector DB).
- Basic tests for each major component (ingest, segmentation, script-gen, TTS,
  visuals, composition).
- LangGraph-based orchestration with durable checkpoints and optional
  human-in-the-loop review steps.

Design principles
- Provider adapter pattern: every external service is accessed through a small
  adapter implementing a base interface; adapters are selected at runtime from
  config by a short priority list (primary: Google; fallbacks: Chinese providers,
  local models).
- Data-first: canonical, serializable JSON representation for chapters and slides
  that is persisted and indexed; artifacts are stored in object storage and
  referenced by URL.
- Incremental/durable execution: the graph persists intermediate artifacts so
  steps can be resumed and manually corrected.
- Cost & privacy controls: caching of expensive generations; opt-in voice
  cloning only after explicit consent; local-only modes for on-prem deployment.

Providers (recommended defaults + Chinese fallbacks)
- LLM & embeddings
  - Primary: Google Vertex AI (Gemini / Vertex Embeddings). Good latency,
    integrated infra on GCP.
  - Fallbacks: OpenAI (when needed), or local `sentence-transformers` for
    embeddings. Chinese alternatives: Baidu ERNIE, Alibaba Tongyi, Tencent
    Wenxin (adapter plugin pattern).
- OCR
  - Primary: Google Cloud Vision (OCR + document OCR)
  - Fallbacks: PyMuPDF/pdfplumber + Tesseract (local OCR), Baidu OCR, Alibaba OCR
- TTS (voices)
  - Primary: Google Cloud Text-to-Speech (SSML and batch synthesis)
  - Fallbacks: Azure Cognitive Services (viseme events for lip-sync), ElevenLabs
    for expressive voices. Chinese providers: iFLYTEK, Alibaba Cloud TTS,
    Baidu TTS.
- Image / text -> image / short video
  - Primary: Stability.ai (Stable Diffusion / SDXL) or Replicate-hosted models
  - For full avatar or script->video: Runway / Synthesia (enterprise). Chinese
    alternatives: Alibaba / Baidu image/video offerings where accessible.
- Vector DB & retrieval
  - Primary: Pinecone (managed) or Vertex Matching; fallback: Qdrant
    (self-hosted). For China use self-hosted Qdrant + MinIO for artifact storage.
- Storage
  - Primary: Google Cloud Storage
  - Fallbacks: AWS S3 or MinIO (self-hosted) for China/offline setups.

How to switch providers
- All external services are configured via a single YAML config file
  `config/providers.yaml` (example in repository: `config/providers.example.yaml`).
- Each service has a priority list: the agent will use the first enabled provider
  in that list.
- Region hint and a single `PREFERRED_REGION` environment variable allow
  choosing a China-optimized provider set automatically.

Example (selection strategy)
```
# pseudo-code
config = load_config("config/providers.yaml")
region = os.getenv("PREFERRED_REGION", "global")
llm_provider = choose_provider("llm", config, region)
```
The `choose_provider` function follows: preferred region providers -> global
priority list -> local fallback.

LangGraph graph (conceptual nodes)
- Input nodes
  - PDFIngest(file) —> pages[], embedded_images[], metadata
  - MarkdownIngest(file) —> text, metadata
  - DirectoryScanner(dir) —> list of PDF/MD file entries
- Processing nodes
  - OCRIfNeeded(pages) —> text per page (uses Vision or Tesseract)
  - ChapterSegmenter(text or pages) —> chapters[], canonicalized chapter text
  - Embedder(chapter_chunks) —> embeddings -> vector DB
  - ChapterScriptGenerator(chapter_text) —> structured JSON (slides[])
  - HumanReview(prompted_state) —> approved_state (manual step)
- Content generation nodes (parallel per-slide)
  - VisualGenerator(visual_prompt) —> image/clip path
  - TTSGenerator(speaker_text, ssml) —> audio path (+ viseme/timing if
    supported)
- Composition nodes
  - VideoComposer(slide_images, audio, transitions) —> chapter_video.mp4
  - Merger(chapter_videos) —> final_course_video.mp4
- Persistence & Indexing
  - StorageAdapter (upload artifacts)
  - VectorDBAdapter (upsert chunks)
- Observability
  - Log events and checkpoints to LangSmith or a local audit trail

Data model (canonical JSON)
- Chapter (example)
```
{
  "id": "chapter-01",
  "title": "Intro to Differential Equations",
  "page_range": [1, 12],
  "text": "...normalized chapter text...",
  "summary": "One-paragraph summary",
  "slides": [
    {
      "id": "c01-s01",
      "title": "What is a differential equation?",
      "bullets": ["Definition...", "Examples...", "Why it matters..."],
      "visual_prompt": "a classroom whiteboard showing dy/dx example\nstyle: clean vector diagram",
      "estimated_duration_sec": 60,
      "audio_path": null,
      "image_path": null
    }
  ]
}
```

File layout (recommended starter)
- `agent/` — Python package with small, testable modules
  - `agent/io.py` — ingestion helpers (PDF, Markdown, directory)
  - `agent/segmenter.py` — deterministic chapter-segmentation heuristics + API
  - `agent/script_generator.py` — structured script generation (LLM wrapper
    will be added behind adapter)
  - `agent/adapters/base.py` — adapter base classes for LLM / TTS / Vision /
    Storage / Vector DB / Visual generation
  - `agent/video_composer.py` — combine images+audio -> video (MoviePy/FFmpeg)
- `config/providers.example.yaml` — sample provider configuration and priorities
- `docs/langgraph_agent_plan.md` — this plan file (source of truth)
- `tests/` — basic tests for each component

Milestones and acceptance criteria

Milestone 0 — Decide providers & bootstrapping (1 day)
- Confirm the primary providers to use for LLMs (Vertex AI), TTS (Google
  Cloud TTS), OCR (Google Vision), storage (GCS), embeddings (Vertex Embeddings
  or local). Add the Chinese fallbacks that must be available.
- Acceptance: `config/providers.example.yaml` created.

Milestone 1 — Ingest + segmentation PoC (3–5 days)
- Implement `agent/io.py` and `agent/segmenter.py` with deterministic
  heuristics. Add unit tests.
- LangGraph graph skeleton (nodes for ingest & segmentation) that returns
  `chapters[]` JSON for a sample PDF/MD.
- Acceptance: run a local script that takes a sample PDF and returns
  chapter JSON for manual review.

Milestone 2 — Script generation PoC (LLM stub) (4–7 days)
- Implement `agent/script_generator.py` with a simple deterministic summarizer
  and slide-splitting heuristic; add an LLM adapter stub (Vertex/OpenAI).
- Tests: validate JSON schema and estimated durations.
- Acceptance: for a sample chapter, generate slides with expected structure.

Milestone 3 — TTS + Visual generation (PoC, parallel) (1–2 weeks)
- Add TTS adapter for Google TTS (sample implementation) and Visual adapter
  (Stability/Replicate) with simple caching and retry logic.
- Acceptance: produce per-slide audio + an image for each slide.

Milestone 4 — Video composition + stitching (1 week)
- Implement `VideoComposer` to build per-chapter MP4 from slides and audio.
- Add subtitles (.srt) generation.
- Acceptance: produced chapter video is playable and audio/video sync is
  within expected tolerance (±200 ms typical).

Milestone 5 — Persistence, indexing, and LangGraph durable execution (1–2
weeks)
- Upload artifacts to GCS/MinIO; index chunk embeddings in Pinecone/Qdrant;
  implement checkpoints and resume in LangGraph.
- Acceptance: agent run can resume after killing process and artifacts are
  retrievable.

Milestone 6 — Optional avatar/advanced video generation & production hardening
(2–4 weeks)
- Integrate a paid avatar solution (Synthesia / Runway) or advanced text-to-video
  models; add user-facing human-in-the-loop review step.
- Add cost controls, quotas, per-run cost reporting.

Testing matrix — basic tests to create now
- `tests/test_config.py`: verify `config/providers.example.yaml` parses and
  contains expected top-level keys.
- `tests/test_io.py`: test `read_markdown`, `list_documents`, and PDF-reading
  smoke test (skipped if PyMuPDF not installed).
- `tests/test_segmenter.py`: check `segment_text_into_chapters` on synthetic
  inputs.
- `tests/test_script_generator.py`: check `generate_slide_plan` output schema and
  simple content rules.
- `tests/test_adapters.py`: import base adapter classes and ensure API
  signatures exist.
- `tests/test_video_composer.py`: smoke-test `VideoComposer` path if MoviePy is
  available (test skipped otherwise).

Developer environment & dependencies
- Provide `requirements.txt` with recommended packages (PyMuPDF, pdfplumber,
  moviepy, pyyaml, pytest, langgraph, google-cloud-* SDKs, qdrant-client, pinecone).
- Workflow: local development with Python >= 3.10, optionally containerized for
  production.

Security, privacy & compliance notes
- Voice cloning and personal voice usage must require consent and audit trail.
- Treat uploaded PDFs as potentially copyrighted — provide explicit user
  warnings and optional policy checks before public sharing.
- Store API keys in secrets manager (GCP Secret Manager / Vault) and not in
  repo.

Cost & throttling
- Cache LLM/TTS/image responses using the artifact store and stable prompt
  hashing. Add concurrency limits and rate-limiting for paid APIs.

Next immediate steps (short):
1. Confirm the provider choices for LLM, TTS, OCR, visual generation, storage,
   and vector DB for the PoC. If Google is allowed, proceed with Vertex / GCS
   defaults.
2. Create the repository skeleton and a minimal LangGraph graph that performs
   file ingestion and chapter segmentation using heuristic rules. The tests
   defined here will drive acceptance.

Files created alongside this plan (in this PR)
- `docs/langgraph_agent_plan.md` (this file)
- `config/providers.example.yaml` (provider priority example)
- `agent/` package: `io.py`, `segmenter.py`, `script_generator.py`,
  `adapters/base.py`, `video_composer.py`
- `requirements.txt` (starter)
- `tests/` smoke tests for the components (lightweight, skip heavy deps)

If the provider choices are confirmed, the next work item will be: implement
Milestone 1 `PDF/MD ingestion + chapter segmentation` and create a LangGraph
graph skeleton to run it. After that is green, proceed step-by-step to the
generation and composition milestones.

---

Reference: use `config/providers.example.yaml` to define provider priorities and
`agent/` package as the place for the first, testable components.
