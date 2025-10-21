from __future__ import annotations

import os
from typing import Optional

from .llm import LLMAdapter, DummyLLMAdapter


def get_llm_adapter(provider: Optional[str] = None) -> LLMAdapter:
    """Return an LLM adapter instance chosen by provider or environment.

    Provider may be 'vertex' or 'openai'. If not specified, reads LLM_PROVIDER
    env variable or defaults to 'vertex'. If the requested adapter cannot be
    instantiated (missing deps), falls back to DummyLLMAdapter.
    """
    chosen = provider or os.getenv("LLM_PROVIDER") or "vertex"
    chosen = chosen.lower()
    if chosen == "openai":
        try:
            from .openai_adapter import OpenAIAdapter

            return OpenAIAdapter()
        except Exception:
            return DummyLLMAdapter()
    if chosen in ("vertex", "google", "gcp"):
        try:
            from .google_vertex_adapter import VertexLLMAdapter

            return VertexLLMAdapter()
        except Exception:
            return DummyLLMAdapter()
    # Unknown provider: return dummy
    return DummyLLMAdapter()
