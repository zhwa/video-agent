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
    """Generate minimal but valid PNG images with title text overlay.

    Useful for tests and offline flows. Creates actual PNG files that can be
    used by MoviePy and other tools.
    """

    def generate_image(self, prompt: str, out_path: Optional[str] = None, width: int = 512, height: int = 512, steps: int = 20, seed: Optional[int] = None) -> str:
        out_path = out_path or "workspace/images/dummy.png"
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        
        # Create valid minimal PNG (solid color background)
        png_data = self._create_minimal_png(width, height, prompt)
        with open(out_path, "wb") as f:
            f.write(png_data)
        return out_path
    
    def _create_minimal_png(self, width: int, height: int, text: str) -> bytes:
        """Create a minimal valid PNG file with solid color background.
        
        This produces a valid PNG that can be read by MoviePy and other tools,
        unlike the previous fake header approach.
        """
        import struct
        import zlib
        
        # PNG signature
        png_signature = b'\x89PNG\r\n\x1a\n'
        
        # IHDR chunk (image header): width, height, bit depth, color type, etc.
        # color_type=2 means RGB (3 bytes per pixel), bit_depth=8
        ihdr_data = struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0)
        ihdr_chunk = self._make_chunk(b'IHDR', ihdr_data)
        
        # IDAT chunk (image data) - white background with filter type byte per scanline
        # Filter type 0 = None (unfiltered)
        scanline = b'\x00' + (b'\xff\xff\xff' * width)  # white pixels (0xff, 0xff, 0xff per pixel)
        all_scanlines = scanline * height
        compressed = zlib.compress(all_scanlines, 9)  # Max compression
        idat_chunk = self._make_chunk(b'IDAT', compressed)
        
        # tEXt chunk (text metadata) - store prompt as metadata
        text_data = f"Title\x00{text[:100]}".encode('utf-8')
        text_chunk = self._make_chunk(b'tEXt', text_data)
        
        # IEND chunk (end marker) - empty data
        iend_chunk = self._make_chunk(b'IEND', b'')
        
        return png_signature + ihdr_chunk + idat_chunk + text_chunk + iend_chunk
    
    def _make_chunk(self, chunk_type: bytes, data: bytes) -> bytes:
        """Create a PNG chunk with proper length and CRC."""
        import struct
        import zlib
        
        chunk_data = chunk_type + data
        crc = zlib.crc32(chunk_data) & 0xffffffff
        return struct.pack('>I', len(data)) + chunk_data + struct.pack('>I', crc)
