from __future__ import annotations

import os
from abc import ABC, abstractmethod
from typing import Optional

from ..cache import FileCache, compute_cache_key


class TTSAdapter(ABC):
    """Abstract interface for TTS adapters.

    Implementations must return a local file path to the generated audio file
    (e.g., WAV or MP3) when `synthesize` is called.
    """

    @abstractmethod
    def synthesize(self, text: str, out_path: Optional[str] = None, voice: Optional[str] = None, language: Optional[str] = None) -> str:
        raise NotImplementedError()


class DummyTTSAdapter(TTSAdapter):
    """Deterministic TTS adapter for testing and offline runs.

    It writes the text to a .txt file and returns a file:// URL to this file
    so callers can treat it analogously to real audio output in integration
    tests.
    """

    def synthesize(self, text: str, out_path: Optional[str] = None, voice: Optional[str] = None, language: Optional[str] = None) -> str:
        import os

        out_path = out_path or "workspace/tts/dummy.wav"
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        # For the dummy adapter write a small text file to indicate content
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(text)
        return out_path


class GoogleTTSAdapter(TTSAdapter):
    """Wrapper around google.cloud.texttospeech with caching support.

    This implementation is permissive: if the cloud client is unavailable
    it raises an ImportError so callers can fallback to DummyTTSAdapter
    during tests.
    """

    def __init__(self, credentials: Optional[str] = None, cache_enabled: bool = True):
        self.credentials = credentials or os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
        self.cache = FileCache(enabled=cache_enabled) if cache_enabled else None

    def synthesize(self, text: str, out_path: Optional[str] = None, voice: Optional[str] = None, language: Optional[str] = None) -> str:
        # Check cache first
        cache_key = None
        if self.cache and self.cache.enabled:
            cache_data = {
                "text": text,
                "voice": voice or os.getenv("GOOGLE_TTS_VOICE") or "en-US-Wavenet-D",
                "language": language or os.getenv("GOOGLE_TTS_LANG") or "en-US",
                "provider": "google_tts",
            }
            cache_key = compute_cache_key(cache_data)
            cached_file = self.cache.get(cache_key, extension=".mp3")
            if cached_file:
                # Copy from cache to output path if specified
                if out_path and out_path != cached_file:
                    import shutil
                    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
                    shutil.copy(cached_file, out_path)
                    return out_path
                return cached_file
        
        # Not in cache - generate
        try:
            from google.cloud import texttospeech
        except Exception:
            raise ImportError("google-cloud-texttospeech is required for GoogleTTSAdapter")

        client = texttospeech.TextToSpeechClient()
        synthesis_input = texttospeech.SynthesisInput(text=text)
        # default voice selection
        vname = voice or os.getenv("GOOGLE_TTS_VOICE") or "en-US-Wavenet-D"
        lang = language or os.getenv("GOOGLE_TTS_LANG") or "en-US"
        voice_params = texttospeech.VoiceSelectionParams(language_code=lang, name=vname)
        audio_config = texttospeech.AudioConfig(audio_encoding=texttospeech.AudioEncoding.MP3)

        response = client.synthesize_speech(input=synthesis_input, voice=voice_params, audio_config=audio_config)
        
        # Determine output path
        if not out_path:
            out_path = "workspace/tts/google_tts.mp3"
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        
        # Write audio content
        with open(out_path, "wb") as f:
            f.write(response.audio_content)
        
        # Store in cache
        if self.cache and self.cache.enabled and cache_key:
            self.cache.put(
                cache_key,
                out_path,
                extension=".mp3",
                metadata={
                    "text_length": len(text),
                    "voice": vname,
                    "language": lang,
                }
            )
        
        return out_path
