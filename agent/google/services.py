"""Unified Google AI services: LLM (Gemini), TTS (Cloud TTS), and Image (Imagen).

This module provides a single entry point for all Google AI services used in the
video agent system. It eliminates the need for adapter patterns and factory functions
by providing direct access to Google's AI capabilities.

Usage:
    from agent.google_services import GoogleServices

    google = GoogleServices()

    # Generate text with Gemini
    text = google.generate_text("Explain quantum computing")

    # Generate speech with Google Cloud TTS
    audio = google.synthesize_speech("Hello world", "output.mp3")

    # Generate images with Imagen
    image = google.generate_image("A mountain landscape", "output.png", 1024, 1024)
"""

from __future__ import annotations

import logging
import os
import time
from typing import Dict, Any, Optional
from google import genai
from ..cache import FileCache, compute_cache_key

logger = logging.getLogger(__name__)

# Default models
DEFAULT_LLM_MODEL = "gemini-2.5-flash"
DEFAULT_IMAGE_MODEL = "imagen-3.0-generate-001"

class GoogleServices:
    """Unified Google AI services for LLM, TTS, and Image generation.

    This class provides a single, consistent interface to all Google AI services
    used in the video agent. It uses:
    - google-genai SDK for LLM (Gemini) and Image (Imagen)
    - google-cloud-texttospeech for TTS

    All services use the same GOOGLE_API_KEY for authentication.
    """

    def __init__(
        self,
        llm_model: str | None = None,
        image_model: str | None = None,
        tts_cache_enabled: bool = True
    ):
        """Initialize Google AI services.

        Args:
            llm_model: Override for LLM model (default: gemini-1.5-flash)
            image_model: Override for image model (default: imagen-3.0-generate-001)
            tts_cache_enabled: Whether to enable TTS caching (default: True)
        """
        try:
            # Don't store module reference to avoid pickling issues
            # self.genai = genai  # REMOVED: module references can't be pickled
            # Initialize client with API key from environment
            api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GOOGLE_GENAI_API_KEY")
            if not api_key:
                raise ValueError(
                    "Google API key not found. Set GOOGLE_API_KEY or "
                    "GOOGLE_GENAI_API_KEY environment variable."
                )

            self.client = genai.Client(api_key=api_key)

            # Configure models
            self.llm_model = llm_model or os.getenv("GOOGLE_LLM_MODEL") or DEFAULT_LLM_MODEL
            self.image_model = image_model or os.getenv("GOOGLE_IMAGE_MODEL") or DEFAULT_IMAGE_MODEL

            # TTS cache
            self.tts_cache = FileCache(enabled=tts_cache_enabled) if tts_cache_enabled else None

            logger.info(
                f"Initialized Google services - "
                f"LLM: {self.llm_model}, Image: {self.image_model}, TTS cache: {tts_cache_enabled}"
            )

        except ImportError as e:
            raise ImportError(
                "google-genai library is required for GoogleServices. "
                "Install it with: pip install google-genai"
            ) from e
        except Exception as e:
            logger.error(f"Failed to initialize Google services: {e}")
            raise

    # =========================================================================
    # LLM Methods (Gemini)
    # =========================================================================

    def generate_text(self, prompt: str) -> str:
        """Generate text from a prompt using Gemini.

        Args:
            prompt: Text prompt for generation

        Returns:
            Generated text string

        Raises:
            RuntimeError: If text generation fails
        """
        try:
            response = self.client.models.generate_content(
                model=self.llm_model,
                contents=prompt
            )

            # Extract text from response
            if hasattr(response, 'text'):
                return response.text
            elif hasattr(response, 'candidates') and response.candidates:
                candidate = response.candidates[0]
                if hasattr(candidate, 'content') and hasattr(candidate.content, 'parts'):
                    parts = candidate.content.parts
                    if parts and hasattr(parts[0], 'text'):
                        return parts[0].text

            # Fallback to string representation
            return str(response)

        except Exception as e:
            logger.error(f"Failed to generate text with Gemini: {e}")
            raise RuntimeError(f"Text generation failed: {e}") from e

    def generate_slide_plan(
        self,
        chapter_text: str,
        max_slides: int | None = None,
        run_id: str | None = None,
        chapter_id: str | None = None
    ) -> Dict[str, Any]:
        """Generate slide plan using LLMClient for retry/validation logic.

        This method delegates to LLMClient which handles:
        - Prompt construction
        - JSON parsing and repair
        - Validation
        - Retries with exponential backoff
        - Logging

        Args:
            chapter_text: The chapter content to generate slides from
            max_slides: Maximum number of slides to generate
            run_id: Optional run identifier for tracking
            chapter_id: Optional chapter identifier for tracking

        Returns:
            Dictionary containing slide plan with structure:
            {"slides": [{"id": "s01", "title": "...", ...}, ...]}
        """
        try:
            from ..llm_client import LLMClient
        except Exception as e:
            logger.error(f"Failed to import LLMClient: {e}")
            return {"slides": []}

        max_retries = int(os.getenv("LLM_MAX_RETRIES", "3"))
        out_dir = os.getenv("LLM_OUT_DIR")
        client = LLMClient(max_retries=max_retries, timeout=None, out_dir=out_dir)
        result = client.generate_and_validate(
            self, chapter_text, max_slides=max_slides, run_id=run_id, chapter_id=chapter_id
        )
        return result.get("plan", {"slides": []})

    # =========================================================================
    # TTS Methods (Google Cloud Text-to-Speech)
    # =========================================================================

    def synthesize_speech(
        self,
        text: str,
        out_path: Optional[str] = None,
        voice: Optional[str] = None,
        language: Optional[str] = None
    ) -> str:
        """Synthesize speech from text using Google Cloud TTS.

        Args:
            text: Text to convert to speech
            out_path: Output file path (default: auto-generated)
            voice: Voice name (default: en-US-Wavenet-D)
            language: Language code (default: en-US)

        Returns:
            Path to generated audio file (MP3 format)

        Note:
            This method uses caching to avoid regenerating identical audio.
            Cache is keyed by text, voice, and language.
        """
        # Check cache first
        cache_key = None
        if self.tts_cache and self.tts_cache.enabled:
            cache_data = {
                "text": text,
                "voice": voice or os.getenv("GOOGLE_TTS_VOICE") or "en-US-Wavenet-D",
                "language": language or os.getenv("GOOGLE_TTS_LANG") or "en-US",
                "provider": "google_tts",
            }
            cache_key = compute_cache_key(cache_data)
            cached_file = self.tts_cache.get(cache_key, extension=".mp3")
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
        except ImportError as e:
            raise ImportError(
                "google-cloud-texttospeech is required for TTS. "
                "Install it with: pip install google-cloud-texttospeech"
            ) from e

        try:
            client = texttospeech.TextToSpeechClient()
            synthesis_input = texttospeech.SynthesisInput(text=text)

            # Configure voice
            vname = voice or os.getenv("GOOGLE_TTS_VOICE") or "en-US-Wavenet-D"
            lang = language or os.getenv("GOOGLE_TTS_LANG") or "en-US"
            voice_params = texttospeech.VoiceSelectionParams(
                language_code=lang,
                name=vname
            )
            audio_config = texttospeech.AudioConfig(
                audio_encoding=texttospeech.AudioEncoding.MP3
            )

            response = client.synthesize_speech(
                input=synthesis_input,
                voice=voice_params,
                audio_config=audio_config
            )
        except Exception as e:
            # Handle authentication errors gracefully
            error_msg = str(e)
            if "credentials" in error_msg.lower() or "authentication" in error_msg.lower():
                logger.warning(
                    f"Google Cloud TTS authentication failed: {error_msg}. "
                    "Creating silent audio placeholder. Set up credentials with: "
                    "gcloud auth application-default login"
                )
                # Create a minimal silent MP3 placeholder
                if not out_path:
                    out_path = "workspace/tts/google_tts.mp3"
                os.makedirs(os.path.dirname(out_path), exist_ok=True)
                
                # Write a minimal MP3 header (silent audio)
                with open(out_path, "wb") as f:
                    # Minimal MP3 file (1 second of silence)
                    f.write(b"\xFF\xFB\x90\x00" + b"\x00" * 100)
                
                logger.info(f"Created silent audio placeholder: {out_path}")
                return out_path
            else:
                # Re-raise other errors
                raise

        # Determine output path
        if not out_path:
            out_path = "workspace/tts/google_tts.mp3"
        os.makedirs(os.path.dirname(out_path), exist_ok=True)

        # Write audio content
        with open(out_path, "wb") as f:
            f.write(response.audio_content)

        logger.info(f"Generated speech audio: {out_path}")

        # Store in cache
        if self.tts_cache and self.tts_cache.enabled and cache_key:
            self.tts_cache.put(
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

    # =========================================================================
    # Image Methods (Imagen)
    # =========================================================================

    def _compute_aspect_ratio(self, width: int, height: int) -> str:
        """Convert width/height to aspect ratio string.

        Imagen 3.0 supports: 1:1, 3:4, 4:3, 9:16, 16:9
        """
        ratio = width / height

        # Map to closest supported ratio
        if 0.95 <= ratio <= 1.05:  # Square
            return "1:1"
        elif 0.70 <= ratio <= 0.80:  # Portrait (3:4)
            return "3:4"
        elif 1.25 <= ratio <= 1.40:  # Landscape (4:3)
            return "4:3"
        elif 0.50 <= ratio <= 0.60:  # Tall portrait (9:16)
            return "9:16"
        elif 1.70 <= ratio <= 1.85:  # Wide landscape (16:9)
            return "16:9"
        else:
            # Default to 1:1 for unusual ratios
            logger.warning(
                f"Unusual aspect ratio {ratio:.2f} ({width}x{height}), using 1:1"
            )
            return "1:1"

    def _make_api_call_with_retry(
        self,
        prompt: str,
        aspect_ratio: str,
        max_retries: int = 5
    ):
        """Make API call with exponential backoff for resilience."""
        base_delay = 1.0  # seconds

        for attempt in range(max_retries):
            try:
                response = self.client.models.generate_images(
                    model=self.image_model,
                    prompt=prompt,
                    config=genai.types.GenerateImagesConfig(
                        number_of_images=1,
                        aspect_ratio=aspect_ratio,
                        safety_filter_level="block_only_high",
                        person_generation="allow_adult",
                    ),
                )
                return response

            except Exception as e:
                error_msg = str(e)

                # Check if it's a retryable error
                is_retryable = any(
                    keyword in error_msg.lower()
                    for keyword in ["rate limit", "timeout", "unavailable", "429", "503"]
                )

                if attempt < max_retries - 1 and is_retryable:
                    delay = base_delay * (2 ** attempt)
                    logger.warning(
                        f"API Error (attempt {attempt + 1}/{max_retries}): {error_msg}. "
                        f"Retrying in {delay:.2f}s..."
                    )
                    time.sleep(delay)
                else:
                    logger.error(
                        f"Failed to generate image after {max_retries} attempts: {error_msg}"
                    )
                    raise RuntimeError(
                        f"Failed to generate image with {self.image_model}: {error_msg}"
                    ) from e

    def generate_image(
        self,
        prompt: str,
        out_path: Optional[str] = None,
        width: int = 1024,
        height: int = 1024,
        steps: int = 20,
        seed: Optional[int] = None,
    ) -> str:
        """Generate an image using Google Imagen 3.0.

        Args:
            prompt: Text description of the image to generate
            out_path: Output file path (default: auto-generated)
            width: Image width in pixels (used to compute aspect ratio)
            height: Image height in pixels (used to compute aspect ratio)
            steps: Ignored for Imagen (no control over this)
            seed: Ignored for Imagen (no control over this)

        Returns:
            Path to generated image file

        Note:
            Imagen 3.0 doesn't support exact width/height or seed control.
            Width/height are used to determine aspect ratio (1:1, 3:4, 4:3, 9:16, 16:9).
        """
        # Generate output path if not provided
        if not out_path:
            import hashlib
            prompt_hash = hashlib.md5(prompt.encode()).hexdigest()[:8]
            out_path = f"workspace/images/google_{prompt_hash}.png"

        os.makedirs(os.path.dirname(out_path), exist_ok=True)

        # Compute aspect ratio from dimensions
        aspect_ratio = self._compute_aspect_ratio(width, height)

        logger.info(
            f"Generating image with Google Imagen "
            f"(aspect_ratio={aspect_ratio}): {prompt[:60]}..."
        )

        try:
            # Make API call with retry logic
            response = self._make_api_call_with_retry(prompt, aspect_ratio)

            # Extract image data from response
            if not response or not response.generated_images:
                raise ValueError("Google Imagen returned empty response")

            # Get first generated image
            generated_image = response.generated_images[0]

            # The image data is in the image.image_bytes field
            if hasattr(generated_image, 'image') and hasattr(generated_image.image, 'image_bytes'):
                image_bytes = generated_image.image.image_bytes
            elif hasattr(generated_image, 'image_bytes'):
                image_bytes = generated_image.image_bytes
            else:
                raise ValueError(
                    f"Unexpected response structure from Google Imagen: {type(generated_image)}"
                )

            # Write image to file
            with open(out_path, "wb") as f:
                f.write(image_bytes)

            logger.info(f"Successfully generated image: {out_path}")
            return out_path
            
        except Exception as e:
            error_msg = str(e)
            # Check if it's a model not found error or authentication error
            if "404" in error_msg or "not found" in error_msg.lower() or "authentication" in error_msg.lower():
                logger.warning(
                    f"Google Imagen generation failed: {error_msg}. "
                    f"Creating placeholder image. Set ENABLE_IMAGES=false to skip image generation."
                )
                # Create a minimal placeholder PNG
                with open(out_path, "wb") as f:
                    # Minimal 1x1 PNG (transparent pixel)
                    f.write(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
                           b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc"
                           b"\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82")
                
                logger.info(f"Created placeholder image: {out_path}")
                return out_path
            else:
                # Re-raise other errors
                raise