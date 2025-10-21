from .llm import LLMAdapter, DummyLLMAdapter
from .factory import get_llm_adapter
from .tts import TTSAdapter, DummyTTSAdapter, GoogleTTSAdapter


def get_tts_adapter(provider: str | None = None) -> TTSAdapter:
	chosen = provider or __import__("os").environ.get("TTS_PROVIDER") or "dummy"
	chosen = chosen.lower()
	if chosen == "google":
		try:
			return GoogleTTSAdapter()
		except Exception:
			return DummyTTSAdapter()
	return DummyTTSAdapter()


__all__ = ["LLMAdapter", "DummyLLMAdapter", "get_llm_adapter", "TTSAdapter", "DummyTTSAdapter", "GoogleTTSAdapter", "get_tts_adapter"]
