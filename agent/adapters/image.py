from __future__ import annotations

import os
from abc import ABC, abstractmethod
from typing import Optional

from ..cache import FileCache, compute_cache_key


class ImageAdapter(ABC):
    """Abstract interface for image generation adapters.
    
    All image adapters should support caching via the cache parameter.
    """

    @abstractmethod
    def generate_image(
        self,
        prompt: str,
        out_path: Optional[str] = None,
        width: int = 512,
        height: int = 512,
        steps: int = 20,
        seed: Optional[int] = None,
    ) -> str:
        """Generate an image from a text prompt.
        
        Args:
            prompt: Text description of the image to generate
            out_path: Output file path (default: auto-generated)
            width: Image width in pixels
            height: Image height in pixels
            steps: Number of generation steps (quality vs speed)
            seed: Random seed for reproducibility (optional)
            
        Returns:
            Path to generated image file
        """
        raise NotImplementedError()


class DummyImageAdapter(ImageAdapter):
    """Deterministic image adapter that writes a tiny PNG header to disk.

    Useful for tests and offline flows.
    """

    def generate_image(self, prompt: str, out_path: Optional[str] = None, width: int = 512, height: int = 512, steps: int = 20, seed: Optional[int] = None) -> str:
        out_path = out_path or "workspace/images/dummy.png"
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        # write a minimal PNG header plus prompt bytes to make file non-empty
        png_header = b"\x89PNG\r\n\x1a\n"
        content = png_header + (prompt.encode("utf-8")[:256])
        with open(out_path, "wb") as f:
            f.write(content)
        return out_path
