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
    """Generate silent audio files matching the estimated text duration.

    Useful for tests and offline flows. Creates valid WAV files that can be
    used by MoviePy and other audio tools. Duration is estimated based on
    typical reading speed (~150 words per minute).
    """

    def synthesize(self, text: str, out_path: Optional[str] = None, voice: Optional[str] = None, language: Optional[str] = None) -> str:
        out_path = out_path or "workspace/tts/dummy.wav"
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        
        # Estimate duration: ~150 words per minute = 4 seconds per 10 words
        word_count = len(text.split())
        duration_sec = max(5, (word_count / 150) * 60)
        
        # Generate a valid silent WAV file
        wav_data = self._create_silent_wav(duration_sec, sample_rate=22050)
        with open(out_path, "wb") as f:
            f.write(wav_data)
        return out_path
    
    def _create_silent_wav(self, duration_sec: float, sample_rate: int = 22050) -> bytes:
        """Create a valid WAV file containing silence (all zeros).
        
        WAV format: RIFF header + fmt subchunk + data subchunk
        This produces files that MoviePy can read and use for timing.
        """
        import struct
        
        num_samples = int(duration_sec * sample_rate)
        
        # WAV header parts
        channels = 1  # Mono
        bits_per_sample = 16
        byte_rate = sample_rate * channels * bits_per_sample // 8
        block_align = channels * bits_per_sample // 8
        
        # RIFF header
        riff_header = b'RIFF'
        file_size = 36 + num_samples * channels * bits_per_sample // 8
        riff_header += struct.pack('<I', file_size)
        riff_header += b'WAVE'
        
        # fmt subchunk
        fmt_subchunk = b'fmt '
        fmt_size = 16  # Standard PCM format is 16 bytes
        fmt_subchunk += struct.pack('<I', fmt_size)
        fmt_subchunk += struct.pack('<HHIIHH', 
            1,                  # Audio format (1 = PCM)
            channels,           # Number of channels
            sample_rate,        # Sample rate
            byte_rate,          # Byte rate
            block_align,        # Block align
            bits_per_sample     # Bits per sample
        )
        
        # data subchunk
        data_subchunk = b'data'
        data_size = num_samples * channels * bits_per_sample // 8
        data_subchunk += struct.pack('<I', data_size)
        
        # Audio data (all zeros = silence)
        audio_data = b'\x00\x00' * num_samples
        
        return riff_header + fmt_subchunk + data_subchunk + audio_data


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
