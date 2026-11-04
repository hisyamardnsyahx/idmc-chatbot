"""Compat: ``rag.retrieve`` moved to ``rag.chat.retrieval``.

The new :func:`search` returns :class:`~rag.core.models.Passage` objects;
this shim converts them back to the legacy ``dict`` shape.
"""

from __future__ import annotations

from typing import Any

from .chat import retrieval as _retrieval
from .chat.service import passage_to_dict  # noqa: F401


def dashboard_names() -> list[str]:
    return _retrieval.dashboard_names()


def search(
    query: str, top_k: int = 5, dashboard_name: str | None = None
) -> list[dict[str, Any]]:
    return [passage_to_dict(p) for p in _retrieval.search(query, top_k, dashboard_name)]


def list_charts() -> list[dict[str, Any]]:
    return _retrieval.list_charts()
