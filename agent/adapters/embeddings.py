from __future__ import annotations

from typing import List, Optional


class EmbeddingsAdapter:
    """Abstract embeddings adapter interface (simple, small wrapper)."""

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        raise NotImplementedError()


class DummyEmbeddingsAdapter(EmbeddingsAdapter):
    """Deterministic dummy embeddings using hash-based floats."""

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        results = []
        for t in texts:
            # Simple deterministic embedding: ascii codes scaled
            emb = [float(ord(c) % 97) / 97.0 for c in t[:16]]
            # pad to fixed length
            while len(emb) < 16:
                emb.append(0.0)
            results.append(emb)
        return results
