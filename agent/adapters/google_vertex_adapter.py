from __future__ import annotations

import os
import json
import re
from typing import Dict, Any

from .llm import LLMAdapter, DummyLLMAdapter


class VertexLLMAdapter(LLMAdapter):
    """Adapter for Google Vertex AI / Generative models.

    It attempts to use `google.generativeai` if available, otherwise falls back
    to `google.cloud.aiplatform`. Credentials are read from the environment
    (GOOGLE_APPLICATION_CREDENTIALS or ADC). The model name is taken from
    VERTEX_MODEL env var or defaults to 'text-bison'.
    """

    def __init__(self, model: str | None = None, project: str | None = None, location: str | None = None):
        self.model = model or os.getenv("VERTEX_MODEL") or "text-bison"
        self.project = project or os.getenv("GCP_PROJECT")
        self.location = location or os.getenv("GCP_LOCATION") or "us-central1"

    def generate_slide_plan(self, chapter_text: str, max_slides: int | None = None, run_id: str | None = None, chapter_id: str | None = None) -> Dict[str, Any]:
        # Delegate to LLMClient to get retries, repair, validation and logging
        try:
            from ..llm_client import LLMClient
        except Exception:
            return DummyLLMAdapter().generate_slide_plan(chapter_text, max_slides=max_slides)

        max_retries = int(os.getenv("LLM_MAX_RETRIES", "3"))
        out_dir = os.getenv("LLM_OUT_DIR")
        client = LLMClient(max_retries=max_retries, timeout=None, out_dir=out_dir)
        result = client.generate_and_validate(self, chapter_text, max_slides=max_slides, run_id=run_id, chapter_id=chapter_id)
        return result.get("plan", {"slides": []})

    def generate_from_prompt(self, prompt: str) -> Any:
        # Prefer google.generativeai when available
        try:
            import google.generativeai as genai
            api_key = os.getenv("GOOGLE_API_KEY")
            if api_key:
                genai.configure(api_key=api_key)
            resp = genai.generate_text(model=self.model, input=prompt)
            text = None
            if hasattr(resp, "candidates") and resp.candidates:
                text = resp.candidates[0].output or None
            elif hasattr(resp, "output"):
                text = resp.output
            if text:
                return text
        except Exception:
            pass

        # Try google.cloud.aiplatform if available
        try:
            from google.cloud import aiplatform
            if self.project:
                aiplatform.init(project=self.project, location=self.location)
            try:
                model = aiplatform.TextGenerationModel.from_pretrained(self.model)
                resp = model.predict(prompt)
                return str(resp)
            except Exception:
                pass
        except Exception:
            pass

        # fallback
        return DummyLLMAdapter().generate_from_prompt(prompt)
