"""Process-wide settings for the ``rag`` package.

Loaded once from the environment (``.env`` supported). Import the
``settings`` singleton in application code; tests may monkeypatch its
attributes or build an isolated instance with :func:`load_settings`.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

PACKAGE_DIR = Path(__file__).resolve().parent.parent


def _get_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        raise ValueError(f"{name} must be an integer, got {os.environ.get(name)!r}")


def _get_float(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, default))
    except (TypeError, ValueError):
        raise ValueError(f"{name} must be a number, got {os.environ.get(name)!r}")


@dataclass
class Settings:
    """All tunable behaviour in one validated place."""

    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.8-flash"
    gemini_fallback_models: tuple = (
        "gemini-3.6-flash",
        "gemini-3.5-flash",
    )
    chat_provider: str = "gemini"
    chat_model: str = ""
    chat_fallback_models: tuple = ()
    chat_base_url: str = ""
    chat_api_key: str = ""
    chat_timeout_s: float = 120.0
    chat_reasoning_effort: str = ""
    cors_origins: tuple[str, ...] = (
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:4173",
        "http://127.0.0.1:4173",
    )
    embed_model: str = "gemini-embedding-2"
    collection_name: str = "rag_web_gemini-embedding-2"

    default_top_k: int = 5
    max_top_k: int = 10
    min_score: float = 0.68
    max_chunk_chars: int = 1500
    embed_batch: int = 50
    embed_rpm: int = 90
    max_429_retries: int = 6
    max_tool_roundtrips: int = 5
    history_turns: int = 10

    storage_dir: Path = field(default_factory=lambda: PACKAGE_DIR / "storage")
    chroma_dir: Path = field(default_factory=lambda: PACKAGE_DIR / "storage" / "chroma")
    sessions_dir: Path = field(default_factory=lambda: PACKAGE_DIR / "storage" / "sessions")
    staging_snapshot: Path = field(
        default_factory=lambda: PACKAGE_DIR / "storage" / "staging_snapshot.json"
    )
    ingest_report: Path = field(
        default_factory=lambda: PACKAGE_DIR / "storage" / "ingest_report.json"
    )
    index_meta: Path = field(
        default_factory=lambda: PACKAGE_DIR / "storage" / "rag_index_meta.json"
    )
    default_staging_source: Path = field(
        default_factory=lambda: PACKAGE_DIR.parent / "staging_superset_data.json"
    )


def _get_models(name: str, default: tuple) -> tuple:
    return _get_list(name, default)


def _get_list(name: str, default: tuple) -> tuple:
    raw = os.environ.get(name, "")
    if not raw.strip():
        return default
    return tuple(item.strip() for item in raw.split(",") if item.strip())


def load_settings() -> Settings:
    """Build settings from the environment, failing fast on bad values."""
    storage = Path(os.environ.get("RAG_STORAGE", str(PACKAGE_DIR / "storage")))
    embed_model = os.environ.get("EMBED_MODEL", "gemini-embedding-2")
    s = Settings(
        gemini_api_key=os.environ.get("GEMINI_API_KEY", ""),
        gemini_model=os.environ.get("GEMINI_MODEL", "gemini-3.8-flash"),
        gemini_fallback_models=_get_models(
            "GEMINI_FALLBACK_MODELS", ("gemini-3.6-flash", "gemini-3.5-flash")
        ),
        chat_provider=os.environ.get("CHAT_PROVIDER", "gemini").strip().lower(),
        chat_model=os.environ.get("CHAT_MODEL", "").strip(),
        chat_fallback_models=_get_models("CHAT_FALLBACK_MODELS", ()),
        chat_base_url=os.environ.get("CHAT_BASE_URL", "").strip().rstrip("/"),
        chat_api_key=os.environ.get("CHAT_API_KEY", ""),
        chat_timeout_s=_get_float("CHAT_TIMEOUT_S", 120.0),
        chat_reasoning_effort=os.environ.get("CHAT_REASONING_EFFORT", "").strip().lower(),
        cors_origins=_get_list(
            "RAG_CORS_ORIGINS",
            (
                "http://localhost:5173",
                "http://127.0.0.1:5173",
                "http://localhost:4173",
                "http://127.0.0.1:4173",
            ),
        ),
        embed_model=embed_model,
        collection_name=os.environ.get(
            "VECTOR_COLLECTION", f"rag_web_{embed_model}"
        ).replace(" ", "_"),
        default_top_k=_get_int("RAG_TOP_K", 5),
        max_top_k=_get_int("RAG_MAX_TOP_K", 10),
        min_score=_get_float("VECTOR_MIN_SCORE", 0.68),
        max_chunk_chars=_get_int("RAG_MAX_CHUNK_CHARS", 1500),
        embed_batch=_get_int("EMBED_BATCH", 50),
        embed_rpm=_get_int("EMBED_RPM", 90),
        max_429_retries=_get_int("EMBED_429_RETRIES", 6),
        max_tool_roundtrips=_get_int("RAG_MAX_ROUNDTRIPS", 5),
        history_turns=_get_int("RAG_HISTORY_TURNS", 10),
        storage_dir=storage,
        chroma_dir=Path(os.environ.get("CHROMA_PATH", str(storage / "chroma"))),
        sessions_dir=storage / "sessions",
        staging_snapshot=storage / "staging_snapshot.json",
        ingest_report=storage / "ingest_report.json",
        index_meta=storage / "rag_index_meta.json",
        default_staging_source=Path(
            os.environ.get(
                "STAGING_SOURCE", str(PACKAGE_DIR.parent / "staging_superset_data.json")
            )
        ),
    )
    if s.default_top_k < 1 or s.max_top_k < s.default_top_k:
        raise ValueError("RAG_TOP_K/RAG_MAX_TOP_K inconsistent: need 1 <= TOP_K <= MAX_TOP_K")
    if s.chat_provider not in ("gemini", "openai-compat"):
        raise ValueError("CHAT_PROVIDER must be 'gemini' or 'openai-compat'")
    if s.chat_provider == "openai-compat" and not s.chat_base_url:
        raise ValueError("CHAT_BASE_URL is required when CHAT_PROVIDER=openai-compat")
    if s.embed_batch < 1:
        raise ValueError("EMBED_BATCH must be >= 1")
    if s.max_429_retries < 1:
        raise ValueError("EMBED_429_RETRIES must be >= 1")
    if s.max_tool_roundtrips < 1:
        raise ValueError("RAG_MAX_ROUNDTRIPS must be >= 1")
    return s


def chat_models(cfg: Settings) -> list[str]:
    """Ordered chat models to try: primary then fallbacks."""
    if cfg.chat_provider == "openai-compat":
        models = [cfg.chat_model, *cfg.chat_fallback_models]
    else:
        models = [cfg.gemini_model, *cfg.gemini_fallback_models]
    return [m for m in models if m]


settings = load_settings()
