# Milestone 5 — Persistence, Indexing & Durable Execution

This milestone focuses on making the agent durable and production-ready by
persisting intermediate artifacts, indexing text for retrieval, and adding
checkpoint/resume capabilities.

High-level goals
- Persist all generated artifacts (audio, images, videos, LLM prompts/responses).
- Index document and chapter text into a vector DB for semantic retrieval.
- Add checkpoints and the ability to resume interrupted runs.
- Keep adapters pluggable (GCS/MinIO, Pinecone/Qdrant, Vertex/OpenAI embeddings).

Steps (small, testable)

1) Storage & artifact archival
- Objective: Ensure every generated artifact (audio/image/video, prompts, attempts) is uploaded to the configured storage and a canonical URL is recorded in run metadata.
- Files: `agent/llm_client.py`, `agent/script_generator.py`, `agent/video_composer.py` (ensure all writers use `get_storage_adapter()`), `agent/storage/*`
- Tests: `tests/test_llm_client_archive.py` (archive attempts), `tests/test_asset_uploads.py` (verify urls saved)
- Acceptance: For a run with `STORAGE_PROVIDER=dummy`, artifacts are uploaded to `workspace/storage/*`, and results include `video_url`, `audio_url`, `image_url` entries that are remote URLs when storage adapter configured.

2) Embeddings & Vector DB
- Objective: Add an `EmbeddingsAdapter` and `VectorDBAdapter` with simple implementations (Vertex/OpenAI stub and Qdrant/Pinecone/Dummy) and embed chapter chunks into a vector DB.
- Files: `agent/adapters/embeddings.py`, `agent/adapters/vector_db.py`, `agent/segmenter.py` (expose chunking API)
- Tests: `tests/test_embeddings_adapter.py`, `tests/test_vector_db_adapter.py` (mocking or using in-memory Qdrant)
- Acceptance: A small doc is chunked and upserted to the vector DB; queries return top-k with reasonable ids.

3) Checkpointing & run metadata
- Objective: Record run state and per-node checkpoints to allow resuming runs from the last successful node.
- Files: `agent/langgraph_nodes.py`, `agent/llm_client.py`, `agent/langgraph_runtime.py` (optional)
- Tests: `tests/test_resume_run.py` (simulate interruption and resume; verify no duplicate artifacts and workflow completes)
- Acceptance: The agent can be killed mid-run and restarted; it resumes where it left off.

4) CLI & API to resume runs
- Objective: Add CLI options to list runs, inspect run metadata, and resume a specific run id.
- Files: `agent/cli.py`, small helper `agent/runs.py`
- Tests: `tests/test_cli_resume.py`
- Acceptance: Developers can resume runs using `--resume <run_id>` and view run artifacts.

5) Telemetry & cost accounting (optional)
- Objective: Collect basic timings, tokens (where available), and cost estimates for a run.
- Files: `agent/telemetry.py`, instrumentation in `agent/llm_client.py` and adapters
- Tests: `tests/test_telemetry.py`

Immediate next steps
1. Start with Step 1 (Storage & artifact archival) — add missing upload calls and tests.
2. Then implement Step 2 (Embeddings & Vector DB) — keep adapters pluggable and simple.
