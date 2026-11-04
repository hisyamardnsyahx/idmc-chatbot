"""RAG chatbot web — layered package.

Layout:
    rag/core/      shared settings, JSON I/O, logging, domain types
    rag/pipeline/  offline ingest: chunking, embeddings, Chroma store
    rag/chat/      retrieval, prompt, response formatter, Gemini loop
    rag/sessions/  file-based conversation state
    rag/web/       FastAPI app + schemas (thin HTTP layer)
    rag/docs/      user and operator documentation
"""

from __future__ import annotations

__version__ = "2.0.0"
