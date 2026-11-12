"""API-agnostic domain types passed between pipeline, chat, and web layers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Document:
    """One embedding-ready chunk with scalar-only metadata for Chroma."""

    id: str
    page_content: str
    metadata: dict[str, Any]


@dataclass(frozen=True)
class Passage:
    """One retrieval hit, shaped for the chat model and the API response."""

    dashboard: str
    chart: str
    slice_id: int | str | None
    rows_covered: str
    data_as_of: str
    possibly_outdated: bool
    relevance: float
    content: str
    source_url: str = ""


@dataclass(frozen=True)
class ChatTurn:
    """One history entry forwarded to the chat model."""

    role: str  # "user" | "assistant"
    text: str
