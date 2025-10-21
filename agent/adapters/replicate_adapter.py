from __future__ import annotations

import os
from typing import Optional

from .image import ImageAdapter
from ..cache import FileCache, compute_cache_key


class ReplicateImageAdapter(ImageAdapter):
    """Adapter for Replicate image generation.
    
    Replicate hosts various models including Stable Diffusion, DALL-E, Midjourney-style models.
    This adapter uses the replicate Python client with caching support.
    
    Configuration via environment variables:
    - REPLICATE_API_TOKEN: API token (required)
    - REPLICATE_MODEL: Model to use (default: stability-ai/sdxl)
    - REPLICATE_VERSION: Model version (optional, uses latest if not set)
    """
    
    def __init__(
        self,
        api_token: Optional[str] = None,
        model: Optional[str] = None,
        version: Optional[str] = None,
        cache_enabled: bool = True,
    ):
        self.api_token = api_token or os.getenv("REPLICATE_API_TOKEN")
        self.model = model or os.getenv("REPLICATE_MODEL") or "stability-ai/sdxl"
        self.version = version or os.getenv("REPLICATE_VERSION")
        self.cache = FileCache(enabled=cache_enabled) if cache_enabled else None
    
    def generate_image(
        self,
        prompt: str,
        out_path: Optional[str] = None,
        width: int = 1024,
        height: int = 1024,
        steps: int = 30,
        seed: Optional[int] = None,
    ) -> str:
        """Generate an image using Replicate API.
        
        Args:
            prompt: Text description of the image
            out_path: Output file path (default: workspace/images/replicate_{hash}.png)
            width: Image width
            height: Image height
            steps: Generation steps
            seed: Random seed for reproducibility
            
        Returns:
            Path to generated image file
        """
        # Check cache first
        cache_key = None
        if self.cache and self.cache.enabled:
            cache_data = {
                "prompt": prompt,
                "width": width,
                "height": height,
                "steps": steps,
                "seed": seed,
                "model": self.model,
                "version": self.version,
                "provider": "replicate",
            }
            cache_key = compute_cache_key(cache_data)
            cached_file = self.cache.get(cache_key, extension=".png")
            if cached_file:
                # Copy from cache to output path if specified
                if out_path and out_path != cached_file:
                    import shutil
                    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
                    shutil.copy(cached_file, out_path)
                    return out_path
                return cached_file
        
        # Not in cache - generate
        if not self.api_token:
            raise ValueError(
                "Replicate API token is required. "
                "Set REPLICATE_API_TOKEN environment variable."
            )
        
        try:
            import replicate
        except ImportError:
            raise ImportError(
                "replicate is required for ReplicateImageAdapter. "
                "Install it with: pip install replicate"
            )
        
        # Set API token
        os.environ["REPLICATE_API_TOKEN"] = self.api_token
        
        # Build input parameters
        input_params = {
            "prompt": prompt,
            "width": width,
            "height": height,
            "num_inference_steps": steps,
        }
        
        if seed is not None:
            input_params["seed"] = seed
        
        # Run model
        if self.version:
            # Use specific version
            output = replicate.run(
                f"{self.model}:{self.version}",
                input=input_params
            )
        else:
            # Use latest version
            output = replicate.run(
                self.model,
                input=input_params
            )
        
        # Download image from URL
        # Replicate typically returns a URL or list of URLs
        image_url = None
        if isinstance(output, list) and len(output) > 0:
            image_url = output[0]
        elif isinstance(output, str):
            image_url = output
        else:
            raise RuntimeError(f"Unexpected output format from Replicate: {type(output)}")
        
        # Download image
        import urllib.request
        
        # Determine output path
        if not out_path:
            safe_hash = cache_key[:8] if cache_key else "image"
            out_path = f"workspace/images/replicate_{safe_hash}.png"
        
        os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
        
        # Download from URL
        urllib.request.urlretrieve(image_url, out_path)
        
        # Store in cache
        if self.cache and self.cache.enabled and cache_key:
            self.cache.put(
                cache_key,
                out_path,
                extension=".png",
                metadata={
                    "prompt_length": len(prompt),
                    "width": width,
                    "height": height,
                    "steps": steps,
                    "model": self.model,
                    "image_url": image_url,
                }
            )
        
        return out_path
