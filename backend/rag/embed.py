"""Compat: ``rag.embed`` moved to ``rag.pipeline.embeddings``."""

from __future__ import annotations

from .pipeline.embeddings import (  # noqa: F401
    default_embedder,
    embed_documents,
    embed_query,
    embed_texts,
    set_embedder,
)
