import sys
import types
import json
from agent.adapters.google_vertex_adapter import VertexLLMAdapter


def test_vertex_adapter_with_fake_generativeai(monkeypatch):
    # Fake google.generativeai module
    google = types.ModuleType("google")
    generativeai = types.ModuleType("google.generativeai")

    class FakeResp:
        def __init__(self, output: str):
            self.candidates = [types.SimpleNamespace(output=output)]

    def fake_generate_text(model, input):
        return FakeResp(json.dumps({"slides": [{"id": "s01", "title": "VTest", "bullets": ["x"], "visual_prompt": "v", "estimated_duration_sec": 25, "speaker_notes": "n"}]}))

    generativeai.generate_text = fake_generate_text
    google.generativeai = generativeai

    sys.modules["google"] = google
    sys.modules["google.generativeai"] = generativeai

    adapter = VertexLLMAdapter(model="test-model")
    result = adapter.generate_slide_plan("Alpha. Beta.")
    assert isinstance(result, dict)
    assert "slides" in result
    assert len(result["slides"]) >= 1

    del sys.modules["google.generativeai"]
    del sys.modules["google"]
