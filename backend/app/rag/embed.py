from __future__ import annotations

import hashlib
import logging
import math
import re

from app.core.config import settings

logger = logging.getLogger(__name__)


def _l2_normalize(vec: list[float]) -> list[float]:
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


def mock_embed(text: str, dim: int | None = None) -> list[float]:
    """Deterministic bag-of-words embedding so overlapping text ranks together."""
    dim = dim or settings.embedding_dim
    vec = [0.0] * dim
    tokens = re.findall(r"[a-z0-9]+", text.lower())
    if not tokens:
        tokens = ["empty"]
    for token in tokens:
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        idx = int.from_bytes(digest[:4], "big") % dim
        sign = 1.0 if digest[4] % 2 == 0 else -1.0
        vec[idx] += sign
    return _l2_normalize(vec)


def gemini_embed(
    texts: list[str], task_type: str = "RETRIEVAL_DOCUMENT"
) -> list[list[float]]:
    from google import genai
    from google.genai import types

    last_error: Exception | None = None
    for api_key in settings.gemini_keys:
        try:
            client = genai.Client(api_key=api_key)
            vectors: list[list[float]] = []
            for text in texts:
                result = client.models.embed_content(
                    model="gemini-embedding-001",
                    contents=text,
                    config=types.EmbedContentConfig(
                        task_type=task_type,
                        output_dimensionality=settings.embedding_dim,
                    ),
                )
                values = list(result.embeddings[0].values)
                if len(values) != settings.embedding_dim:
                    raise ValueError(
                        f"Gemini returned {len(values)} embedding dimensions; "
                        f"expected {settings.embedding_dim}"
                    )
                vectors.append(_l2_normalize(values))
            return vectors
        except Exception as exc:
            last_error = exc
            logger.warning("Gemini embedding key failed (%s)", type(exc).__name__)
    assert last_error is not None
    raise last_error


def embed_texts(
    texts: list[str], task_type: str = "RETRIEVAL_DOCUMENT"
) -> list[list[float]]:
    provider = settings.effective_embedding_provider
    if provider == "gemini" and settings.gemini_keys:
        try:
            return gemini_embed(texts, task_type=task_type)
        except Exception as exc:
            logger.warning(
                "Gemini embeddings failed (%s): %s. Using mock embeddings.",
                type(exc).__name__,
                exc,
            )
    return [mock_embed(t) for t in texts]
