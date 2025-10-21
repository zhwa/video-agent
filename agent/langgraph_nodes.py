from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from .io import read_file
from .segmenter import segment_pages_into_chapters, segment_text_into_chapters
from .script_generator import generate_slides_for_chapter
from .parallel import run_tasks_in_threads
import uuid
from .adapters.factory import get_llm_adapter
import os
import warnings


def validate_vertex_credentials() -> bool:
    """Simple check to see whether Vertex credentials are likely present.

    Checks GOOGLE_APPLICATION_CREDENTIALS or GOOGLE_API_KEY environment variables.
    """
    if os.getenv("GOOGLE_APPLICATION_CREDENTIALS"):
        return True
    if os.getenv("GOOGLE_API_KEY"):
        return True
    return False


@dataclass
class LangGraphNodeDef:
    id: str
    type: str
    config: Dict[str, Any]


def build_graph_description(input_path: str) -> Dict[str, Any]:
    """Return a JSON-serializable description of the LangGraph graph for
    an ingest->segment->script workflow.

    This description can be used to instantiate a real LangGraph Graph if the
    library is available. For now it provides a clear structure useful for
    testing and for later conversion to LangGraph nodes.
    """
    nodes: List[LangGraphNodeDef] = []
    nodes.append(LangGraphNodeDef(id="ingest", type="ingest", config={"path": input_path}))
    nodes.append(LangGraphNodeDef(id="segment", type="segment", config={}))
    nodes.append(LangGraphNodeDef(id="script_gen", type="script_generator", config={"adapter": "vertex"}))
    edges = [("ingest", "segment"), ("segment", "script_gen")]
    return {"nodes": [n.__dict__ for n in nodes], "edges": edges}


def run_graph_description(desc: Dict[str, Any], llm_adapter=None) -> Dict[str, Any]:
    """Execute the simple description using local functions (no external
    LangGraph runtime). This executes the ingest->segment->script workflow
    sequentially.
    """
    nodes = {n["id"]: n for n in desc.get("nodes", [])}
    results: Dict[str, Any] = {}
    # Ingest
    ingest_cfg = nodes["ingest"]["config"]
    path = ingest_cfg.get("path")
    info = read_file(path)
    results["ingest"] = info
    # Segment
    if info.get("type") == "pdf":
        chapters = segment_pages_into_chapters(info.get("pages", []))
    else:
        chapters = segment_text_into_chapters(info.get("text", ""))
    results["segment"] = chapters
    # Script generation using provided adapter or provider-based adapter
    if llm_adapter is None:
        # Try selecting one from environment; factory defaults to 'vertex'
        adapter = get_llm_adapter()
    else:
        adapter = llm_adapter
    # If adapter is Vertex and credentials appear missing, warn the user
    try:
        adapter_name = adapter.__class__.__name__
        if "Vertex" in adapter_name or adapter_name.lower().startswith("vertex"):
            if not validate_vertex_credentials():
                warnings.warn(
                    "Vertex credentials not detected in environment. The adapter may fall back or fail. "
                    "Set GOOGLE_APPLICATION_CREDENTIALS or GOOGLE_API_KEY to enable Vertex.",
                    RuntimeWarning,
                )
    except Exception:
        pass
    # Generate a run id for logging/artifacts
    run_id = str(uuid.uuid4())

    # Allow parallel per-chapter generation when configured.
    try:
        max_workers = int(os.getenv("MAX_WORKERS", "1"))
    except Exception:
        max_workers = 1
    try:
        rate_limit = float(os.getenv("LLM_RATE_LIMIT", "0"))
        if rate_limit <= 0:
            rate_limit = None
    except Exception:
        rate_limit = None

    script_results = []
    if max_workers and max_workers > 1 and len(chapters) > 1:
        # Build tasks
        tasks = []
        for c in chapters:
            def make_task(ch):
                def _task():
                    return generate_slides_for_chapter(ch, adapter, run_id=run_id)

                return _task

            tasks.append(make_task(c))
        script_results = run_tasks_in_threads(tasks, max_workers=max_workers, rate_limit=rate_limit)
    else:
        for c in chapters:
            script_results.append(generate_slides_for_chapter(c, adapter, run_id=run_id))
    results["script_gen"] = script_results
    # Expose which adapter was used (for debugging and audit)
    try:
        results["llm_adapter_used"] = adapter.__class__.__name__
    except Exception:
        results["llm_adapter_used"] = str(adapter)
    return results
