"""Google AI services integration for video agent.

This module provides unified access to Google's AI services:
- Gemini LLM (via google-genai)
- Imagen 3.0 image generation  
- Cloud Text-to-Speech
- Local file storage

Main exports:
- GoogleServices: Unified service class (handles LLM, TTS, and image generation)
- get_storage_adapter: Local storage helper
- DummyStorageAdapter: Local file storage implementation
"""

from .services import GoogleServices
from .storage import get_storage_adapter, DummyStorageAdapter

__all__ = [
    "GoogleServices",
    "get_storage_adapter",
    "DummyStorageAdapter",
]