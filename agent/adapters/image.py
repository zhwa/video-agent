from __future__ import annotations

import os
from abc import ABC, abstractmethod
from typing import Optional


class ImageAdapter(ABC):
    """Abstract interface for image generation adapters."""

    @abstractmethod
    def generate_image(self, prompt: str, out_path: Optional[str] = None, width: int = 512, height: int = 512, steps: int = 20, seed: Optional[int] = None) -> str:
        """Synthesize an image for the given prompt and return a local file path."""


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
