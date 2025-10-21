import sys
import types
import json
from agent.adapters.openai_adapter import OpenAIAdapter
from agent.llm_client import LLMClient


def test_llm_client_repair_logs(monkeypatch, tmp_path):
    # Create fake openai module that returns invalid JSON first, then valid JSON
    module = types.ModuleType("openai")

    calls = {"i": 0}

    def fake_chat_create(**kwargs):
        calls["i"] += 1
        if calls["i"] == 1:
            return {"choices": [{"message": {"content": "I am not JSON"}}]}
        return {"choices": [{"message": {"content": json.dumps({"slides": [{"id": "s01", "title": "Repaired", "bullets": ["a"], "visual_prompt": "v", "estimated_duration_sec": 30, "speaker_notes": "n"}]})}}]}

    class ChatCompletion:
        @staticmethod
        def create(**kwargs):
            return fake_chat_create(**kwargs)

    module.ChatCompletion = ChatCompletion
    sys.modules["openai"] = module

    adapter = OpenAIAdapter(api_key="x", model="test-model")
    out_dir = str(tmp_path / "out")
    client = LLMClient(max_retries=3, out_dir=out_dir)
    res = client.generate_and_validate(adapter, "One. Two.")
    assert res.get("plan")
    attempts = res.get("attempts")
    assert len(attempts) >= 1
    # Assert attempts were logged to out_dir
    assert (tmp_path / "out" / "run" / "chapter" / "attempt_01_prompt.txt").exists()

    del sys.modules["openai"]
