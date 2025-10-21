from __future__ import annotations

import os
from abc import ABC, abstractmethod
from typing import Optional


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
    """Wrapper around google.cloud.texttospeech.

    This implementation is permissive: if the cloud client is unavailable
    it raises an ImportError so callers can fallback to DummyTTSAdapter
    during tests.
    """

    def __init__(self, credentials: Optional[str] = None):
        self.credentials = credentials or os.getenv("GOOGLE_APPLICATION_CREDENTIALS")

    def synthesize(self, text: str, out_path: Optional[str] = None, voice: Optional[str] = None, language: Optional[str] = None) -> str:
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
        out_path = out_path or "workspace/tts/google_tts.mp3"
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        with open(out_path, "wb") as f:
            f.write(response.audio_content)
        return out_path
