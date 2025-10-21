# Lecture Agent — Next Milestones & TODO

This document lists the next concrete engineering tasks to bring the Lecture Agent from PoC to a production-capable pipeline. Each entry includes files to edit, tests to add, acceptance criteria, and a rough effort estimate.

1) Finish adapter → LLMClient integration (verify + tests)
- Files: `agent/adapters/openai_adapter.py`, `agent/adapters/google_vertex_adapter.py`, any other adapters under `agent/adapters/`
- Tests: `tests/test_openai_adapter.py`, `tests/test_vertex_adapter.py` (update to assert LLMClient attempts are logged and that `generate_from_prompt` is used)
- Acceptance: All adapters call `LLMClient.generate_and_validate` for plan generation by default; logs written to `LLM_OUT_DIR` when set; unit tests (mocked remote SDKs) pass.
- Effort: small

2) Storage adapter for artifacts (images, audio, video)
- Files: add `agent/storage/__init__.py`, `agent/storage/storage_adapter.py`, `agent/storage/gcs_adapter.py`, `agent/storage/minio_adapter.py`.
- Tests: `tests/test_storage_adapter.py` (mock GCS/MinIO SDKs or use a local MinIO test container via test fixtures).
- Acceptance: `upload_file`/`download_file` API works and returns canonical URLs; tests validate upload path composition and error handling.
- Effort: medium

3) Persist prompts/responses and archive to storage
- Files: enhance `agent/llm_client.py` to support an optional `storage_adapter` parameter and an `archive_attempts_to_storage` method.
- Tests: `tests/test_llm_client_archive.py` (use Dummy storage adapter to assert files uploaded)
- Acceptance: When `LLM_OUT_DIR` is set the client writes locally; when `storage_adapter` provided, attempts are archived to remote storage and local temp removed if configured.
- Effort: small

4) Parallelize per-chapter generation with throttling
- Files: `agent/parallel.py` or modify `agent/langgraph_nodes.py` to run chapter-level jobs concurrently; configuration via env `MAX_WORKERS` and `LLM_RATE_LIMIT`.
- Tests: `tests/test_parallel_generation.py` (use Dummy adapter with artificial delays to assert concurrency and respect for `MAX_WORKERS`).
- Acceptance: End-to-end run with 10 small chapters executes concurrently limited by `MAX_WORKERS`; no race conditions on shared files.
- Effort: medium

5) TTS pipeline
- Files: `agent/adapters/tts.py` (interface), `agent/adapters/google_tts.py`, `agent/adapters/elevenlabs_tts.py`, `agent/adapters/iflytek_tts.py` (optional Chinese providers)
- Tests: `tests/test_tts_adapters.py` (mock SDKs, assert returned local file paths are uploaded to storage adapter)
- Acceptance: Per-slide audio is generated and persisted; CLI option allows selection of voice/provider; test coverage for failure fallbacks.
- Effort: medium

6) Image generation adapters
- Files: `agent/adapters/image.py` (interface), `agent/adapters/stability_adapter.py`, `agent/adapters/replicate_adapter.py` (and any provider-specific wrappers)
- Tests: `tests/test_image_adapter.py` (mock remote calls, test that generated images are uploaded)
- Acceptance: For each slide, a visual is generated from `visual_prompt` and stored; deterministic fallback images available in offline mode.
- Effort: medium

7) Video composition & muxing
- Files: `agent/video/compositor.py` (MoviePy wrapper and ffmpeg integration), `agent/video/__init__.py`.
- Tests: `tests/test_compositor.py` (smoke test combining short audio+image to a short video and validating file existence and duration)
- Acceptance: Per-chapter MP4 files are created matching slide durations and with embedded audio; final video is uploaded to configured storage.
- Effort: medium to large

8) Switch from PoC runner → real LangGraph runtime + observability
- Files: add `agent/langgraph_runtime.py` (LangGraph node definitions and Graph builder), update `agent/langgraph_nodes.py` to emit LangGraph nodes when available.
- Tests: `tests/test_langgraph_integration.py` (mock LangGraph runtime or use a lightweight in-process executor)
- Acceptance: Long-running runs can be resumed; checkpoints and run metadata recorded in `LLM_OUT_DIR` and optionally in remote storage; LangSmith traces available when configured.
- Effort: medium to large

9) Cost estimation, token/accounting, and telemetry
- Files: `agent/telemetry.py` to capture durations, token usage (when provider supports it), and estimate costs per call; integrate with LLM adapters to report tokens/cost.
- Tests: `tests/test_telemetry.py`.
- Acceptance: Per-run summarized cost estimation is produced and attached to run metadata.
- Effort: small to medium

10) CI, linting, and contract tests
- Files: `.github/workflows/ci.yml`, add `pytest.ini`, add `mypy`/`flake8` config
- Tests: Add contract tests that validate adapters comply with `LLMAdapter`/`StorageAdapter`/`TTSAdapter` interfaces.
- Acceptance: CI runs unit tests and linters on push; contract tests run in CI with mocks.
- Effort: small

11) Sample notebooks and example datasets
- Files: add `examples/README.md`, `examples/sample_lecture.md`, optional Jupyter notebook `examples/run_demo.ipynb`.
- Acceptance: A developer can run the demo end-to-end locally with dummy adapters to produce one short video.
- Effort: small

12) Productionization checklist
- Items: secrets management (use Secret Manager or local vault), quota limits and rate limiting, content moderation hooks, localization support for Chinese providers, monitoring/alerting.
- Acceptance: Security review and runbook prepared.
- Effort: large

Immediate next actions (this sprint)
- Create storage adapter scaffolding and tests (Task 2)
- Add `storage_adapter` option to `LLMClient` and implement archive flow (Task 3)
- Add concurrency runner and basic `MAX_WORKERS` config (Task 4)


