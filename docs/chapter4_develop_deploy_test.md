# Chapter 4 — Develop, Deploy and Test

This document provides instructions for running, testing and deploying the
Video Agent locally and in a simple production environment.

Quickstart (local)
1. Create a Python virtual environment with Python >= 3.10
2. Install dev dependencies

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

3. Run tests

```powershell
python -m pytest -q
```

Running the agent
```powershell
python -m agent.cli path/to/lesson.md --out workspace/out --provider vertex
```

Testing notes
- Use dummy adapters to avoid network calls in CI.
- MoviePy-based tests are skipped unless MoviePy is installed.

Deploy

1. Prepare a VM or container with Python 3.10+.
2. Install production dependencies and the chosen provider SDKs.
3. Configure environment variables for the selected providers and credentials.
4. Run the agent via the CLI or as a scheduled job.
