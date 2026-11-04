"""Compat: ``rag.chunk`` moved to ``rag.pipeline.chunking``.

The new API returns :class:`~rag.core.models.Document` objects; the
helpers below preserve the legacy ``dict`` shape for old callers.
"""

from __future__ import annotations

from typing import Any

from .core.models import Document
from .pipeline.chunking import chunk_charts as _chunk_charts
from .pipeline.chunking import format_row, format_value  # noqa: F401


def _to_dict(doc: Document) -> dict[str, Any]:
    return {"id": doc.id, "page_content": doc.page_content, "metadata": doc.metadata}


def chunk_chart(chart: dict[str, Any], max_chars: int | None = None) -> list[dict[str, Any]]:
    from .pipeline import chunking as chunk_mod

    return [_to_dict(d) for d in chunk_mod.chunk_chart(chart, max_chars)]


def chunk_charts(charts: dict[Any, dict[str, Any]]) -> list[dict[str, Any]]:
    return [_to_dict(d) for d in _chunk_charts(charts)]
