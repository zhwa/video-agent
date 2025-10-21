from .llm import LLMAdapter, DummyLLMAdapter
from .factory import get_llm_adapter
from .tts import TTSAdapter, DummyTTSAdapter, GoogleTTSAdapter
from .image import ImageAdapter, DummyImageAdapter


def get_tts_adapter(provider: str | None = None) -> TTSAdapter:
	"""Factory to get TTS adapter by provider name.
	
	Supported providers:
	- 'google': Google Cloud Text-to-Speech
	- 'elevenlabs': ElevenLabs TTS
	- 'dummy': Deterministic dummy (testing)
	
	If provider is None, reads from TTS_PROVIDER env var or defaults to 'dummy'.
	"""
	chosen = provider or __import__("os").environ.get("TTS_PROVIDER") or "dummy"
	chosen = chosen.lower()
	
	if chosen == "google":
		try:
			return GoogleTTSAdapter()
		except Exception:
			return DummyTTSAdapter()
	
	if chosen == "elevenlabs":
		try:
			from .elevenlabs_tts import ElevenLabsTTSAdapter
			return ElevenLabsTTSAdapter()
		except Exception:
			return DummyTTSAdapter()
	
	return DummyTTSAdapter()


def get_image_adapter(provider: str | None = None) -> ImageAdapter:
	"""Factory to get image generation adapter by provider name.
	
	Supported providers:
	- 'stability': Stability.ai (Stable Diffusion)
	- 'replicate': Replicate (various models)
	- 'dummy': Deterministic dummy (testing)
	
	If provider is None, reads from IMAGE_PROVIDER env var or defaults to 'dummy'.
	"""
	chosen = provider or __import__("os").environ.get("IMAGE_PROVIDER") or "dummy"
	chosen = chosen.lower()
	
	if chosen == "stability":
		try:
			from .stability_adapter import StabilityImageAdapter
			return StabilityImageAdapter()
		except Exception:
			return DummyImageAdapter()
	
	if chosen == "replicate":
		try:
			from .replicate_adapter import ReplicateImageAdapter
			return ReplicateImageAdapter()
		except Exception:
			return DummyImageAdapter()
	
	return DummyImageAdapter()


__all__ = [
	"LLMAdapter",
	"DummyLLMAdapter",
	"get_llm_adapter",
	"TTSAdapter",
	"DummyTTSAdapter",
	"GoogleTTSAdapter",
	"get_tts_adapter",
	"ImageAdapter",
	"DummyImageAdapter",
	"get_image_adapter",
]
