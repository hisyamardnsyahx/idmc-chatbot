"""Compat: flat ``rag.config`` names now live in ``rag.core.config``.

New code should ``from rag.core.config import settings`` and read
attributes from the ``settings`` singleton.
"""

from __future__ import annotations

from .core.config import load_settings, settings  # noqa: F401

RAG_DIR = settings.storage_dir.parent
STORAGE_DIR = settings.storage_dir
CHROMA_DIR = settings.chroma_dir
SESSIONS_DIR = settings.sessions_dir

GEMINI_API_KEY = settings.gemini_api_key
GEMINI_MODEL = settings.gemini_model
GEMINI_FALLBACK_MODELS = settings.gemini_fallback_models
CHAT_PROVIDER = settings.chat_provider
CHAT_MODEL = settings.chat_model
CHAT_FALLBACK_MODELS = settings.chat_fallback_models
CHAT_BASE_URL = settings.chat_base_url
CHAT_API_KEY = settings.chat_api_key
CHAT_TIMEOUT_S = settings.chat_timeout_s
EMBED_MODEL = settings.embed_model
COLLECTION_NAME = settings.collection_name

DEFAULT_TOP_K = settings.default_top_k
MAX_TOP_K = settings.max_top_k
MIN_SCORE = settings.min_score
MAX_CHUNK_CHARS = settings.max_chunk_chars
EMBED_BATCH = settings.embed_batch
EMBED_RPM = settings.embed_rpm
MAX_429_RETRIES = settings.max_429_retries
MAX_TOOL_ROUNDTRIPS = settings.max_tool_roundtrips
HISTORY_TURNS = settings.history_turns

STAGING_SNAPSHOT = settings.staging_snapshot
INGEST_REPORT = settings.ingest_report
INDEX_META = settings.index_meta
DEFAULT_STAGING_SOURCE = settings.default_staging_source
