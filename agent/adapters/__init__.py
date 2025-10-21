from .llm import LLMAdapter, DummyLLMAdapter
from .factory import get_llm_adapter
from .tts import TTSAdapter, DummyTTSAdapter, GoogleTTSAdapter
from .image import ImageAdapter, DummyImageAdapter
from .embeddings import EmbeddingsAdapter, DummyEmbeddingsAdapter
from .vector_db import VectorDBAdapter, InMemoryVectorDB

def get_tts_adapter(provider: str | None = None) -> TTSAdapter:
    """Factory to get TTS adapter by provider name.

    Supported providers:
    - 'google': Google Cloud Text-to-Speech
    - 'elevenlabs': ElevenLabs TTS
    - 'dummy': Deterministic dummy (testing)

    If provider is None, reads from TTS_PROVIDER env var or defaults to 'dummy'.
    """
    import os

    chosen = provider or os.getenv("TTS_PROVIDER") or "dummy"
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
    import os

    chosen = provider or os.getenv("IMAGE_PROVIDER") or "dummy"
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
    "EmbeddingsAdapter",
    "DummyEmbeddingsAdapter",
    "VectorDBAdapter",
    "InMemoryVectorDB",
]

def get_embeddings_adapter(provider: str | None = None) -> EmbeddingsAdapter:
    # For now return dummy; in future support Vertex/OpenAI
    return DummyEmbeddingsAdapter()

def get_vector_db_adapter(provider: str | None = None) -> VectorDBAdapter:
    # For now return in-memory adapter; expand for Qdrant/Pinecone
    return InMemoryVectorDB()