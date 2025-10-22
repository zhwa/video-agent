from __future__ import annotations

import logging
import os
from typing import Optional

from .llm import LLMAdapter, DummyLLMAdapter

logger = logging.getLogger(__name__)

def get_llm_adapter(provider: Optional[str] = None) -> LLMAdapter:
    """Return an LLM adapter instance chosen by provider or environment.

    Provider may be 'google' or 'openai'. If not specified, reads LLM_PROVIDER
    env variable or defaults to 'google'. If the requested adapter cannot be
    instantiated (missing deps), falls back to DummyLLMAdapter.
    """
    chosen = provider or os.getenv("LLM_PROVIDER") or "google"
    chosen = chosen.lower()
    logger.debug("Resolving LLM adapter: %s", chosen)

    if chosen == "openai":
        try:
            from .openai_adapter import OpenAIAdapter
            adapter = OpenAIAdapter()
            logger.info("Initialized OpenAI LLM adapter")
            return adapter
        except ImportError as e:
            logger.warning("OpenAI adapter not available (openai not installed), falling back to dummy: %s", e)
            return DummyLLMAdapter()
        except Exception as e:
            logger.warning("Failed to initialize OpenAI adapter, falling back to dummy: %s", e)
            return DummyLLMAdapter()

    if chosen in ("google", "vertex", "gcp", "gemini"):
        try:
            from .google_adapter import GoogleAdapter
            adapter = GoogleAdapter()
            logger.info("Initialized Google (Gemini) LLM adapter")
            return adapter
        except ImportError as e:
            logger.warning("Google adapter not available (google-genai not installed), falling back to dummy: %s", e)
            return DummyLLMAdapter()
        except Exception as e:
            logger.warning("Failed to initialize Google adapter, falling back to dummy: %s", e)
            return DummyLLMAdapter()

    # Unknown provider: return dummy
    logger.info("Using Dummy LLM adapter")
    return DummyLLMAdapter()

def get_tts_adapter(provider: Optional[str] = None):
    """Return a TTS adapter instance chosen by provider or environment.

    Supported providers:
    - 'google': Google Cloud Text-to-Speech
    - 'elevenlabs': ElevenLabs TTS
    - 'dummy': Deterministic dummy (testing)

    If provider is None, reads from TTS_PROVIDER env var or defaults to 'dummy'.
    """
    from .tts import DummyTTSAdapter, GoogleTTSAdapter

    chosen = provider or os.getenv("TTS_PROVIDER") or "dummy"
    chosen = chosen.lower()
    logger.debug("Resolving TTS adapter: %s", chosen)

    if chosen == "google":
        try:
            adapter = GoogleTTSAdapter()
            logger.info("Initialized Google Cloud TTS adapter")
            return adapter
        except ImportError as e:
            logger.warning("Google TTS adapter not available (google-cloud-texttospeech not installed), falling back to dummy: %s", e)
            return DummyTTSAdapter()
        except Exception as e:
            logger.warning("Failed to initialize Google TTS adapter, falling back to dummy: %s", e)
            return DummyTTSAdapter()

    if chosen == "elevenlabs":
        try:
            from .elevenlabs_tts import ElevenLabsTTSAdapter
            adapter = ElevenLabsTTSAdapter()
            logger.info("Initialized ElevenLabs TTS adapter")
            return adapter
        except ImportError as e:
            logger.warning("ElevenLabs TTS adapter not available (elevenlabs not installed), falling back to dummy: %s", e)
            return DummyTTSAdapter()
        except Exception as e:
            logger.warning("Failed to initialize ElevenLabs TTS adapter, falling back to dummy: %s", e)
            return DummyTTSAdapter()

    logger.info("Using Dummy TTS adapter")
    return DummyTTSAdapter()

def get_image_adapter(provider: Optional[str] = None):
    """Return an image adapter instance chosen by provider or environment.

    Supported providers:
    - 'google' or 'imagen': Google Imagen 3.0 (Nano Banana)
    - 'dummy': Deterministic dummy (testing)

    If provider is None, reads from IMAGE_PROVIDER env var or defaults to 'google'.
    """
    from .image import DummyImageAdapter

    chosen = provider or os.getenv("IMAGE_PROVIDER") or "google"
    chosen = chosen.lower()
    logger.debug("Resolving image adapter: %s", chosen)

    if chosen in ("google", "imagen", "gcp", "gemini"):
        try:
            from .google_adapter import GoogleAdapter
            adapter = GoogleAdapter()
            logger.info("Initialized Google (Imagen) image adapter")
            return adapter
        except ImportError as e:
            logger.warning("Google adapter not available (google-genai not installed), falling back to dummy: %s", e)
            return DummyImageAdapter()
        except Exception as e:
            logger.warning("Failed to initialize Google adapter, falling back to dummy: %s", e)
            return DummyImageAdapter()

    logger.info("Using Dummy image adapter")
    return DummyImageAdapter()