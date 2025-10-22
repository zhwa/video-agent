from __future__ import annotations

import os
import json
import re
from typing import Dict, Any

from .llm import LLMAdapter, DummyLLMAdapter


class OpenAIAdapter(LLMAdapter):
    """Adapter for OpenAI API (reads OPENAI_API_KEY from env by default).

    This adapter calls the OpenAI ChatCompletion API (if `openai` is installed)
    and expects the model to return a JSON payload describing slides. If the
    LLM response can't be parsed as JSON, it falls back to a deterministic
    local heuristic (DummyLLMAdapter).
    """

    def __init__(self, api_key: str | None = None, model: str | None = None):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.model = model or os.getenv("OPENAI_MODEL") or "gpt-4o-mini"

    def generate_slide_plan(self, chapter_text: str, max_slides: int | None = None, run_id: str | None = None, chapter_id: str | None = None) -> Dict[str, Any]:
        # Delegate to the centralized LLMClient for generation, retries, repair and validation
        try:
            from ..llm_client import LLMClient
        except Exception:
            # If LLMClient not importable for some reason, fallback to local deterministic adapter
            return DummyLLMAdapter().generate_slide_plan(chapter_text, max_slides=max_slides)

        max_retries = int(os.getenv("LLM_MAX_RETRIES", "3"))
        out_dir = os.getenv("LLM_OUT_DIR")
        client = LLMClient(max_retries=max_retries, timeout=None, out_dir=out_dir)
        result = client.generate_and_validate(self, chapter_text, max_slides=max_slides, run_id=run_id, chapter_id=chapter_id)
        return result.get("plan", {"slides": []})

    def generate_from_prompt(self, prompt: str) -> Any:
        # Lazy import so module import doesn't fail if openai is not installed
        try:
            import openai
        except Exception:
            raise ImportError("openai library is required for OpenAIAdapter but not installed")

        if self.api_key:
            openai.api_key = self.api_key

        # Try chat-based call first
        try:
            response = openai.ChatCompletion.create(
                model=self.model,
                messages=[{"role": "system", "content": "You are a slide plan generator."}, {"role": "user", "content": prompt}],
                temperature=0.2,
            )
            # Extract textual content
            content = None
            if isinstance(response, dict):
                choices = response.get("choices") or []
                if choices:
                    first = choices[0]
                    if isinstance(first.get("message"), dict):
                        content = first["message"].get("content")
                    else:
                        content = first.get("text") or first.get("message")
            else:
                try:
                    content = response.choices[0].message.content
                except Exception:
                    content = None
            if content:
                return content
        except Exception:
            pass

        # Fallback to legacy completion endpoint
        try:
            response = openai.Completion.create(model=self.model, prompt=prompt, max_tokens=1200, temperature=0.2)
            if isinstance(response, dict):
                choices = response.get("choices") or []
                if choices:
                    return choices[0].get("text")
            try:
                return response.choices[0].text
            except Exception:
                return str(response)
        except Exception as e:
            return {"error": str(e)}
