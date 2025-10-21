import sys
import types
import json
from agent.adapters.openai_adapter import OpenAIAdapter


def test_openai_adapter_parses_json(monkeypatch):
    # Create a fake openai module
    module = types.ModuleType("openai")

    def fake_create(**kwargs):
        return {"choices": [{"message": {"content": json.dumps({"slides": [{"id": "s01", "title": "Test", "bullets": ["a"], "visual_prompt": "v", "estimated_duration_sec": 30, "speaker_notes": "n"}]})}}]}

    class ChatCompletion:
        @staticmethod
        def create(**kwargs):
            return fake_create(**kwargs)

    module.ChatCompletion = ChatCompletion
    sys.modules["openai"] = module

    adapter = OpenAIAdapter(api_key="x", model="test-model")
    result = adapter.generate_slide_plan("Sentence one. Sentence two.")
    assert isinstance(result, dict)
    assert "slides" in result
    assert len(result["slides"]) >= 1

    # Clean up
    del sys.modules["openai"]
