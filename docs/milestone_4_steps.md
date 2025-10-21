# Milestone 4 — Video Composition & Stitching

This document breaks Milestone 4 into small, executable steps so we can
implement, test, and verify each part incrementally.

Each step contains: objective, files to edit, tests to add, acceptance criteria,
and a rough effort estimate. Work from the top down and stop after each step to
run tests and confirm behavior.

---

## Step 1 — CLI + Pipeline entry for composition

- Objective: Expose the video composer via the CLI and a pipeline entry so a
  user can produce per-chapter videos for an existing run.
- Files: `agent/cli.py`, `agent/video_composer.py`
- Tests: `tests/test_cli_compose.py` (invoke CLI with `--compose` or new flag and assert video file(s) created/uploaded)
- Acceptance: `python -m agent.cli sample.md --compose` triggers composer and produces per-chapter `*.mp4` and `.srt` artifacts (file or uploaded URL).
- Effort: small (1–2 days)

---

## Step 2 — Concurrency & resource control for composition

- Objective: Compose chapter videos in parallel with configurable concurrency and rate limits. Add a `--compose-workers` flag and environment variables for tuning.
- Files: `agent/video_composer.py`, `agent/parallel.py`, `agent/cli.py`, optional `agent/composer_runner.py`
- Tests: `tests/test_compose_workers.py` (simulate slow composer, assert concurrency respects `MAX_COMPOSER_WORKERS`), test for `COMPOSITION_RATE_LIMIT`.
- Acceptance: Parallel composition honors `MAX_COMPOSER_WORKERS` and rate limit; overall process stable under memory use.
- Effort: medium (2–4 days)

---

## Step 3 — Subtitles & captions enhancements

- Objective: Improve SRT generation (line-wrap, per-bullet timing), add optional VTT output, and ensure accurate timing using audio durations.
- Files: `agent/video_composer.py` (SRT/VTT helper), `agent/cli.py` flags
- Tests: `tests/test_srt_formatting.py` (validate SRT format, line-wrapping and timing), `tests/test_vtt_output.py` (optional)
- Acceptance: SRT/VTT files are syntactically correct; timestamps aligned to slide durations; optional per-bullet timing available.
- Effort: small (1–2 days)

---

## Step 4 — Merge chapter videos into final course video

- Objective: Concatenate per-chapter MP4s into a single course MP4 with simple transitions and metadata.
- Files: `agent/video_composer.py` (add `merge_videos`), `agent/cli.py` (flag)
- Tests: `tests/test_merge_videos.py` (concat two small MP4s and check final file exists and duration approx equals sum)
- Acceptance: `course.mp4` exists, plays, and duration within ±200 ms of expected; file uploaded via storage adapter when configured.
- Effort: small (1–2 days)

---

## Step 5 — End-to-end tests & smoke runs

- Objective: Add a short end-to-end test that runs ingest → segment → script → generate assets → compose per-chapter videos → merge course video, using dummy adapters when possible.
- Files: `tests/test_end_to_end_full_pipeline.py`
- Tests: simulate a short markdown file and run the full pipeline; check artifacts and final output.
- Acceptance: End-to-end tests run quickly with dummy adapters; PRs must pass these tests.
- Effort: medium (2–4 days)

---

## Step 6 — Productionization & performance optimizations (future)

- Objective: Optimize ffmpeg/ moviepy invocation, improve caching of intermediate artifacts, support GPU acceleration, and add resource-aware scheduling.
- Files: `Dockerfile`, `requirements.txt`, `agent/video_composer.py`, optional `agent/worker_pool.py`
- Tests: performance micro-benchmarks and stress tests (CI optional)
- Acceptance: Reduced memory/CPU usage for large runs; CI job with quick performance checks.
- Effort: large (1–2 weeks)

---

## Immediate next step suggestion

Start with Step 1 (CLI + pipeline entry) so we can trigger composition end-to-end from the command line. After that, implement Step 2 (concurrency) to speed up multi-chapter runs.

If you'd like, I can implement Step 1 now — would you like me to proceed?
