from __future__ import annotations

from typing import Dict, List, Optional, Tuple
import math


class VectorDBAdapter:
    def upsert(self, id: str, vector: List[float], metadata: Optional[Dict] = None):
        raise NotImplementedError()

    def query(self, vector: List[float], top_k: int = 5) -> List[Tuple[str, float]]:
        raise NotImplementedError()


class InMemoryVectorDB(VectorDBAdapter):
    """Simple in-memory vector DB for tests and development."""

    def __init__(self):
        self._store: Dict[str, Dict] = {}

    def upsert(self, id: str, vector: List[float], metadata: Optional[Dict] = None):
        self._store[id] = {"vector": vector, "metadata": metadata}

    def _cosine_similarity(self, a: List[float], b: List[float]) -> float:
        # Compute cosine similarity
        dot = sum(x * y for x, y in zip(a, b))
        na = math.sqrt(sum(x * x for x in a))
        nb = math.sqrt(sum(x * x for x in b))
        if na == 0 or nb == 0:
            return 0.0
        return dot / (na * nb)

    def query(self, vector: List[float], top_k: int = 5) -> List[Tuple[str, float]]:
        scores = []
        for id, rec in self._store.items():
            sim = self._cosine_similarity(vector, rec["vector"])
            scores.append((id, sim))
        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:top_k]
