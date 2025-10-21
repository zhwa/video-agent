from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from .io import read_file
from .segmenter import segment_pages_into_chapters, segment_text_into_chapters
from .script_generator import generate_slides_for_chapter
from .parallel import run_tasks_in_threads
import uuid
from .adapters.factory import get_llm_adapter
from .adapters import get_embeddings_adapter, get_vector_db_adapter
import os
import threading
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


def run_graph_description(desc: Dict[str, Any], llm_adapter=None, resume_run_id: str | None = None) -> Dict[str, Any]:
    """Execute the simple description using local functions (no external
    LangGraph runtime). This executes the ingest->segment->script workflow
    sequentially.
    """
    nodes = {n["id"]: n for n in desc.get("nodes", [])}
    results: Dict[str, Any] = {}
    # Ingest
    ingest_cfg = nodes["ingest"]["config"]
    path = ingest_cfg.get("path")
    # Generate a run id for logging/artifacts or resume existing
    if resume_run_id:
        run_id = resume_run_id
    else:
        run_id = str(uuid.uuid4())
    checkpoint = {}
    try:
        from .runs import create_run, load_checkpoint

        create_run(path, run_id)
        checkpoint = load_checkpoint(run_id)
    except Exception:
        checkpoint = {}

    # If checkpoint indicates ingest done, reuse
    if checkpoint.get("ingest"):
        info = checkpoint.get("ingest")
    else:
        info = read_file(path)
    results["ingest"] = info
    try:
        from .runs import save_checkpoint

        save_checkpoint(run_id, "ingest", info)
    except Exception:
        pass
    # Segment -- reuse checkpoint if available
    if checkpoint.get("segment"):
        chapters = checkpoint.get("segment")
    else:
        if info.get("type") == "pdf":
            chapters = segment_pages_into_chapters(info.get("pages", []))
        else:
            chapters = segment_text_into_chapters(info.get("text", ""))
    results["segment"] = chapters
    try:
        from .runs import save_checkpoint

        save_checkpoint(run_id, "segment", chapters)
    except Exception:
        pass
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
    # reconstruct existing script_gen results from checkpoint (if any)
    existing_script = checkpoint.get("script_gen") or []
    existing_map = {s.get("chapter_id"): s for s in existing_script}

    # Build list of chapters that still need generation
    missing_chapters = [c for c in chapters if c.get("id") not in existing_map]

    # If there are already some results, avoid parallel generation to reduce races
    parallel_allowed = max_workers and max_workers > 1 and len(chapters) > 1 and not existing_script
    if parallel_allowed:
        # Build tasks
        tasks = []
        for c in chapters:
            def make_task(ch):
                def _task():
                    return generate_slides_for_chapter(ch, adapter, run_id=run_id)

                return _task

            tasks.append(make_task(c))
        # perform parallel generation and save each completed chapter incrementally
        # we use a lock to serialize checkpoint writes
        ckpt_lock = threading.Lock()

        def _wrap_task(ch):
            def _t():
                res = generate_slides_for_chapter(ch, adapter, run_id=run_id)
                # merge into checkpoint
                try:
                    from .runs import load_checkpoint, save_checkpoint

                    with ckpt_lock:
                        cur = load_checkpoint(run_id)
                        cur_list = cur.get("script_gen") or []
                        # avoid duplicates when resuming
                        if not any(x.get("chapter_id") == res.get("chapter_id") for x in cur_list):
                            cur_list.append(res)
                        save_checkpoint(run_id, "script_gen", cur_list)
                except Exception:
                    pass
                return res

            return _t

        wrapped_tasks = [ _wrap_task(c) for c in chapters ]
        script_results = run_tasks_in_threads(wrapped_tasks, max_workers=max_workers, rate_limit=rate_limit)
    else:
        # If there are existing script results, only generate missing chapters.
        if existing_script:
            # preserve order according to chapters
            script_results = [existing_map.get(c.get("id")) for c in chapters if existing_map.get(c.get("id"))]
            # generate missing chapters sequentially and append
            for c in missing_chapters:
                res = generate_slides_for_chapter(c, adapter, run_id=run_id)
                script_results.append(res)
                try:
                    from .runs import save_checkpoint

                    save_checkpoint(run_id, "script_gen", script_results)
                except Exception:
                    pass
        else:
            for c in chapters:
                script_results.append(generate_slides_for_chapter(c, adapter, run_id=run_id))
    results["script_gen"] = script_results
    try:
        from .runs import save_checkpoint

        save_checkpoint(run_id, "script_gen", script_results)
    except Exception:
        pass
    # Embeddings: index chapter chunks into vector DB (skip if already done)
    try:
        if checkpoint.get("vector_db"):
            results["vector_db"] = checkpoint.get("vector_db")
        else:
            emb_adapter = get_embeddings_adapter()
            vecdb = get_vector_db_adapter()
            # Simple chunker: split chapter text into 1024-char chunks
            for chap in chapters:
                text = chap.get("text", "")
                chunks = [text[i : i + 1024] for i in range(0, len(text), 1024)]
                if not chunks:
                    continue
                embeddings = emb_adapter.embed_texts(chunks)
                for i, vec in enumerate(embeddings):
                    id = f"{chap.get('id')}_chunk_{i}"
                    vecdb.upsert(id, vec, metadata={"chapter_id": chap.get('id'), "chunk_index": i})
            results["vector_db"] = {"indexed_chapters": len(chapters)}
            try:
                from .runs import save_checkpoint

                save_checkpoint(run_id, "vector_db", results["vector_db"])
            except Exception:
                pass
    except Exception:
        # best-effort: continue if embedding/indexing not available
        pass
    # Expose which adapter was used (for debugging and audit)
    try:
        results["llm_adapter_used"] = adapter.__class__.__name__
    except Exception:
        results["llm_adapter_used"] = str(adapter)
    # Expose run id so callers can reuse the same id for downstream artifacts
    results["run_id"] = run_id
    return results