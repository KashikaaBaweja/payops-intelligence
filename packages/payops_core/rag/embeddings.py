from __future__ import annotations

import hashlib
import math
import re
from typing import Protocol

from payops_core.config import get_settings

_TOKEN = re.compile(r"[a-z0-9_]+")


class Embedder(Protocol):
    dim: int

    def embed(self, text: str) -> list[float]: ...


class HashingEmbedder:
    """Deterministic local embeddings. No API key required."""

    def __init__(self, dim: int | None = None) -> None:
        self.dim = dim or get_settings().embedding_dim

    def embed(self, text: str) -> list[float]:
        vector = [0.0] * self.dim
        tokens = _TOKEN.findall(text.lower())
        if not tokens:
            return vector
        for token in tokens:
            digest = hashlib.md5(token.encode("utf-8"), usedforsecurity=False).hexdigest()
            index = int(digest, 16) % self.dim
            vector[index] += 1.0
        return _l2_normalize(vector)


def cosine(left: list[float], right: list[float]) -> float:
    score = sum(a * b for a, b in zip(left, right, strict=True))
    return round(float(score), 6)


def _l2_normalize(vector: list[float]) -> list[float]:
    norm = math.sqrt(sum(value * value for value in vector))
    if norm == 0:
        return vector
    return [value / norm for value in vector]


def get_embedder() -> Embedder:
    return HashingEmbedder()
