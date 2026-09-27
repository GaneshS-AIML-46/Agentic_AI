from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

Source = Literal[
    "database",
    "forecast_model",
    "agent_reasoning",
    "solver",
    "rag_document",
    "user_query",
]


class Provenanced(BaseModel):
    """A numeric or textual fact tagged with where it came from."""

    value: Any
    source: Source
    note: str | None = None


class EvidenceHit(BaseModel):
    document_id: str
    title: str
    snippet: str
    score: float
    source_path: str | None = None
    doc_type: str | None = None
