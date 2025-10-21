from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Optional

from .langgraph_nodes import build_graph_description, run_graph_description
from .adapters.factory import get_llm_adapter


def main():
    p = argparse.ArgumentParser(description="Run the LangGraph lecture agent (PoC)")
    p.add_argument("path", help="Path to input file (PDF/MD) or directory")
    p.add_argument("--provider", help="LLM provider override (vertex|openai)")
    p.add_argument("--out", help="Output folder to write results", default="workspace/out")
    p.add_argument("--llm-retries", help="Max retries for LLM client", type=int, default=None)
    p.add_argument("--llm-out", help="Directory for LLM attempt logs", default=None)
    p.add_argument("--max-workers", help="Max concurrent chapter generation workers", type=int, default=None)
    p.add_argument("--llm-rate", help="LLM rate limit in calls per second", type=float, default=None)
    args = p.parse_args()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Configure LLM client via environment (simple approach)
    if args.llm_retries is not None:
        import os

        os.environ.setdefault("LLM_MAX_RETRIES", str(args.llm_retries))
    if args.llm_out:
        import os

        os.environ.setdefault("LLM_OUT_DIR", args.llm_out)
    if args.max_workers is not None:
        import os

        os.environ.setdefault("MAX_WORKERS", str(args.max_workers))
    if args.llm_rate is not None:
        import os

        os.environ.setdefault("LLM_RATE_LIMIT", str(args.llm_rate))

    desc = build_graph_description(args.path)
    adapter = None
    if args.provider:
        adapter = get_llm_adapter(args.provider)
    result = run_graph_description(desc, llm_adapter=adapter)
    out_file = out_dir / (Path(args.path).stem + "_results.json")
    out_file.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Results written to:", out_file)


if __name__ == "__main__":
    main()
