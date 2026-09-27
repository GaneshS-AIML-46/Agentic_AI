from __future__ import annotations

import hashlib
import math
import random

from app.core.config import settings


def _l2_normalize(vec: list[float]) -> list[float]:
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


def mock_embed(text: str, dim: int | None = None) -> list[float]:
    dim = dim or settings.embedding_dim
    seed = int(hashlib.sha256(text.encode("utf-8")).hexdigest(), 16) % (2**32)
    rng = random.Random(seed)
    return _l2_normalize([rng.gauss(0, 1) for _ in range(dim)])


def gemini_embed(texts: list[str]) -> list[list[float]]:
    from google import genai

    client = genai.Client(api_key=settings.resolved_gemini_key)
    vectors: list[list[float]] = []
    for text in texts:
        result = client.models.embed_content(
            model="text-embedding-004",
            contents=text,
        )
        values = list(result.embeddings[0].values)
        if len(values) < settings.embedding_dim:
            values = values + [0.0] * (settings.embedding_dim - len(values))
        vectors.append(_l2_normalize(values[: settings.embedding_dim]))
    return vectors


def embed_texts(texts: list[str]) -> list[list[float]]:
    provider = settings.effective_embedding_provider
    if provider == "gemini" and settings.resolved_gemini_key:
        try:
            return gemini_embed(texts)
        except Exception:
            pass
    return [mock_embed(t) for t in texts]
