"""Unified Google adapter for both LLM (Gemini) and Image generation (Imagen).

This adapter consolidates all Google AI services into a single adapter:
- LLM: Gemini models (gemini-pro, gemini-1.5-flash, etc.)
- Image: Imagen 3.0 (imagen-3.0-generate-001)

Uses the google-genai library for a unified API experience.
"""

from __future__ import annotations

import logging
import os
import time
from typing import Dict, Any, Optional

from .llm import LLMAdapter, DummyLLMAdapter
from .image import ImageAdapter

logger = logging.getLogger(__name__)

# Default models
DEFAULT_LLM_MODEL = "gemini-1.5-flash"
DEFAULT_IMAGE_MODEL = "imagen-3.0-generate-001"

class GoogleAdapter(LLMAdapter, ImageAdapter):
    """Unified adapter for Google's AI services (Gemini LLM + Imagen).

    Supports both text generation (LLM) and image generation using the
    google-genai SDK with a single API key.
    """

    def __init__(self, llm_model: str | None = None, image_model: str | None = None):
        """Initialize the Google GenAI client.

        Args:
            llm_model: Override for LLM model (default: gemini-1.5-flash)
            image_model: Override for image model (default: imagen-3.0-generate-001)
        """
        try:
            from google import genai
            self.genai = genai

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

            logger.info(
                f"Initialized Google adapter - LLM: {self.llm_model}, Image: {self.image_model}"
            )

        except ImportError as e:
            raise ImportError(
                "google-genai library is required for GoogleAdapter. "
                "Install it with: pip install google-genai"
            ) from e
        except Exception as e:
            logger.error(f"Failed to initialize Google adapter: {e}")
            raise

    # -------------------------------------------------------------------------
    # LLM Methods (from LLMAdapter interface)
    # -------------------------------------------------------------------------

    def generate_slide_plan(
        self,
        chapter_text: str,
        max_slides: int | None = None,
        run_id: str | None = None,
        chapter_id: str | None = None
    ) -> Dict[str, Any]:
        """Generate slide plan using LLMClient for retry/validation logic."""
        try:
            from ..llm_client import LLMClient
        except Exception:
            return DummyLLMAdapter().generate_slide_plan(
                chapter_text, max_slides=max_slides
            )

        max_retries = int(os.getenv("LLM_MAX_RETRIES", "3"))
        out_dir = os.getenv("LLM_OUT_DIR")
        client = LLMClient(max_retries=max_retries, timeout=None, out_dir=out_dir)
        result = client.generate_and_validate(
            self, chapter_text, max_slides=max_slides, run_id=run_id, chapter_id=chapter_id
        )
        return result.get("plan", {"slides": []})

    def generate_from_prompt(self, prompt: str) -> Any:
        """Generate text from a prompt using Gemini models.

        Args:
            prompt: Text prompt for generation

        Returns:
            Generated text string
        """
        try:
            # Use the google-genai client for text generation
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
            logger.error(f"Failed to generate text with Google LLM: {e}")
            return DummyLLMAdapter().generate_from_prompt(prompt)

    # -------------------------------------------------------------------------
    # Image Methods (from ImageAdapter interface)
    # -------------------------------------------------------------------------

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

    def _make_api_call_with_retry(self, prompt: str, aspect_ratio: str, max_retries: int = 5):
        """Make API call with exponential backoff for resilience."""
        base_delay = 1.0  # seconds

        for attempt in range(max_retries):
            try:
                # Use generate_images method for Imagen 3.0
                response = self.client.models.generate_images(
                    model=self.image_model,
                    prompt=prompt,
                    config=self.genai.types.GenerateImagesConfig(
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