from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional


def runs_dir() -> Path:
    return Path(os.getenv("RUNS_DIR") or "workspace/runs")


def ensure_run_dir(run_id: str) -> Path:
    d = runs_dir() / run_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def create_run(path: str, run_id: Optional[str] = None) -> str:
    import uuid

    if not run_id:
        run_id = str(uuid.uuid4())
    d = ensure_run_dir(run_id)
    meta = {"path": path, "created": datetime.utcnow().isoformat(), "nodes": {}}
    (d / "metadata.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    return run_id


def get_run_metadata(run_id: str) -> Optional[Dict]:
    d = runs_dir() / run_id
    meta_file = d / "metadata.json"
    if not meta_file.exists():
        return None
    return json.loads(meta_file.read_text(encoding="utf-8"))


def save_checkpoint(run_id: str, node: str, data: Dict) -> None:
    d = ensure_run_dir(run_id)
    chk_file = d / "checkpoint.json"
    if chk_file.exists():
        current = json.loads(chk_file.read_text(encoding="utf-8"))
    else:
        current = {}
    current[node] = data
    current.setdefault("completed", {})[node] = datetime.utcnow().isoformat()
    chk_file.write_text(json.dumps(current, ensure_ascii=False, indent=2), encoding="utf-8")


def load_checkpoint(run_id: str) -> Dict:
    chk_file = runs_dir() / run_id / "checkpoint.json"
    if not chk_file.exists():
        return {}
    return json.loads(chk_file.read_text(encoding="utf-8"))


def list_runs() -> Dict:
    d = runs_dir()
    if not d.exists():
        return {}
    result = {}
    for child in d.iterdir():
        if child.is_dir():
            meta = get_run_metadata(child.name)
            result[child.name] = meta
    return result
