"""Compat: ``rag.store`` moved to ``rag.pipeline.vector_store``.

``index_documents`` keeps its legacy signature: pass plain dicts and it
embeds via :mod:`rag.pipeline.embeddings` internally.
"""

from __future__ import annotations

from typing import Any

from .core.models import Document
from .pipeline import embeddings as _embeddings
from .pipeline.vector_store import get_collection, get_stats, query  # noqa: F401
from .pipeline.vector_store import index_documents as _index_documents


def index_documents(docs: list[dict[str, Any] | Document]) -> dict[str, int]:
    objects = [
        d if isinstance(d, Document) else Document(
            id=d["id"], page_content=d["page_content"], metadata=d["metadata"]
        )
        for d in docs
    ]
    return _index_documents(objects, _embeddings.embed_documents)
