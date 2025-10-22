"""Google AI services integration for video agent.

This module provides unified access to Google's AI services:
- Gemini LLM (via google-genai)
- Imagen 3.0 image generation  
- Cloud Text-to-Speech
- Local file storage

Main exports:
- GoogleServices: Unified service class
- get_storage_adapter: Local storage helper
- DummyTTSAdapter, GoogleTTSAdapter: TTS implementations
- DummyImageAdapter: Image placeholder
"""

from .services import GoogleServices
from .storage import get_storage_adapter, DummyStorageAdapter
from .tts import TTSAdapter, DummyTTSAdapter, GoogleTTSAdapter, get_tts_adapter
from .image import ImageAdapter, DummyImageAdapter

__all__ = [
    "GoogleServices",
    "get_storage_adapter",
    "get_tts_adapter",
    "DummyStorageAdapter",
    "TTSAdapter",
    "DummyTTSAdapter",
    "GoogleTTSAdapter",
    "ImageAdapter",
    "DummyImageAdapter",
]
