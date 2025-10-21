# Video Agent

This repository contains a small, pluggable pipeline that converts lecture
content (PDF/Markdown) into structured slides, synthesized audio, and final
video lectures.

See `docs/` for detailed documentation:
- `docs/chapter1_overview.md` — high-level overview of the project
- `docs/chapter2_how_it_works.md` — pipeline flow and LangGraph mapping
- `docs/chapter3_components.md` — component-by-component notes
- `docs/chapter4_develop_deploy_test.md` — development, deployment and test

Run tests locally:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m pytest -q
```
