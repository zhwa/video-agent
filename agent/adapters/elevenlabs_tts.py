from __future__ import annotations

import os
from typing import Optional

from .tts import TTSAdapter
from ..cache import FileCache, compute_cache_key


class ElevenLabsTTSAdapter(TTSAdapter):
    """Adapter for ElevenLabs Text-to-Speech API.
    
    ElevenLabs provides high-quality, expressive voice synthesis with voice cloning
    capabilities. Requires API key and supports caching.
    
    Configuration via environment variables:
    - ELEVENLABS_API_KEY: API key (required)
    - ELEVENLABS_VOICE_ID: Default voice ID (optional, uses default voice if not set)
    - ELEVENLABS_MODEL: Model to use (default: eleven_monolingual_v1)
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        voice_id: Optional[str] = None,
        model: Optional[str] = None,
        cache_enabled: bool = True,
    ):
        self.api_key = api_key or os.getenv("ELEVENLABS_API_KEY")
        self.voice_id = voice_id or os.getenv("ELEVENLABS_VOICE_ID")
        self.model = model or os.getenv("ELEVENLABS_MODEL") or "eleven_monolingual_v1"
        self.cache = FileCache(enabled=cache_enabled) if cache_enabled else None
    
    def synthesize(
        self,
        text: str,
        out_path: Optional[str] = None,
        voice: Optional[str] = None,
        language: Optional[str] = None,
    ) -> str:
        """Synthesize speech using ElevenLabs API.
        
        Args:
            text: Text to synthesize
            out_path: Output file path (default: workspace/tts/elevenlabs_{voice}.mp3)
            voice: Voice ID to use (overrides default)
            language: Ignored (ElevenLabs uses model for language)
            
        Returns:
            Path to generated audio file
        """
        # Check cache first
        cache_key = None
        voice_id = voice or self.voice_id
        
        if self.cache and self.cache.enabled:
            cache_data = {
                "text": text,
                "voice_id": voice_id,
                "model": self.model,
                "provider": "elevenlabs",
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
        if not self.api_key:
            raise ValueError(
                "ElevenLabs API key is required. "
                "Set ELEVENLABS_API_KEY environment variable."
            )
        
        try:
            from elevenlabs import generate, save
        except ImportError:
            raise ImportError(
                "elevenlabs is required for ElevenLabsTTSAdapter. "
                "Install it with: pip install elevenlabs"
            )
        
        # Use default voice if not specified
        if not voice_id:
            # ElevenLabs default voice ID (Rachel)
            voice_id = "21m00Tcm4TlvDq8ikWAM"
        
        # Generate audio
        # Note: elevenlabs.generate() returns audio bytes
        audio = generate(
            text=text,
            voice=voice_id,
            model=self.model,
            api_key=self.api_key,
        )
        
        # Determine output path
        if not out_path:
            safe_voice = (voice_id[:8] if len(voice_id) > 8 else voice_id).replace("/", "_")
            out_path = f"workspace/tts/elevenlabs_{safe_voice}.mp3"
        
        os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
        
        # Save audio (elevenlabs.save handles writing bytes to file)
        save(audio, out_path)
        
        # Store in cache
        if self.cache and self.cache.enabled and cache_key:
            self.cache.put(
                cache_key,
                out_path,
                extension=".mp3",
                metadata={
                    "text_length": len(text),
                    "voice_id": voice_id,
                    "model": self.model,
                }
            )
        
        return out_path
