"""Gemini embeddings behind a small injectable interface.

Production code uses :class:`GeminiEmbedder`. Tests inject a fake via
:func:`set_embedder` (or pass vectors straight to the store layer).
"""

from __future__ import annotations

import functools
import logging
import re
import time
from typing import Any, Protocol

from ..core import config as config_mod
from ..core.errors import translate_provider_error

log = logging.getLogger("rag.pipeline.embed")


class Embedder(Protocol):
    def embed_query(self, query: str) -> list[float]: ...
    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...


class GeminiEmbedder:
    """Batching + throttle + 429 retry wrapper around ``embed_content``."""

    def __init__(self) -> None:
        # One long-lived SDK client per embedder. A temporary
        # genai.Client() without a surviving reference can be garbage
        # collected mid-request, closing its httpx client under us.
        self._client_obj = None

    def _client(self):
        if self._client_obj is None:
            if not config_mod.settings.gemini_api_key:
                raise RuntimeError("GEMINI_API_KEY is missing — set it in .env")
            from google import genai

            self._client_obj = genai.Client(api_key=config_mod.settings.gemini_api_key)
        return self._client_obj

    @staticmethod
    def _is_v2() -> bool:
        return "embedding-2" in config_mod.settings.embed_model

    def _call(self, batch: list[str], kind: str) -> list[list[float]]:
        from google.genai import errors, types

        if self._is_v2():
            fmt = (
                (lambda t: f"task: search result | query: {t}")
                if kind == "query"
                else (lambda t: f"title: none | text: {t}")
            )
            contents: Any = [
                types.Content(parts=[types.Part.from_text(text=fmt(t))]) for t in batch
            ]
            req_config = None
        else:
            contents = batch
            req_config = types.EmbedContentConfig(
                task_type="RETRIEVAL_QUERY" if kind == "query" else "RETRIEVAL_DOCUMENT"
            )

        for attempt in range(1, config_mod.settings.max_429_retries + 1):
            started = time.monotonic()
            try:
                resp = self._client().models.embed_content(
                    model=config_mod.settings.embed_model, contents=contents, config=req_config
                )
                break
            except errors.ClientError as e:
                if getattr(e, "code", None) != 429 or attempt == config_mod.settings.max_429_retries:
                    raise translate_provider_error(e, operation="membuat embedding") from e
                m = re.search(r"retry in ([\d.]+)s", str(e))
                delay = float(m.group(1)) + 1 if m else 20.0 * attempt
                log.warning(
                    "Rate limited (429); sleeping %.0fs (attempt %d/%d)",
                    delay,
                    attempt,
                    config_mod.settings.max_429_retries,
                )
                time.sleep(delay)
            except errors.ServerError as e:
                raise translate_provider_error(e, operation="membuat embedding") from e
            except Exception as e:  # network/SDK failure — translate, never leak raw
                raise translate_provider_error(e, operation="membuat embedding") from e

        if kind != "query" and config_mod.settings.embed_rpm > 0:
            wait = len(batch) * 60 / config_mod.settings.embed_rpm - (time.monotonic() - started)
            if wait > 0:
                time.sleep(wait)
        return [e.values for e in resp.embeddings]

    def _embed_texts(self, texts: list[str], kind: str) -> list[list[float]]:
        vectors: list[list[float]] = []
        for i in range(0, len(texts), config_mod.settings.embed_batch):
            vectors.extend(self._call(texts[i : i + config_mod.settings.embed_batch], kind))
        if len(vectors) != len(texts):
            raise RuntimeError(f"Expected {len(texts)} embeddings, got {len(vectors)}.")
        return vectors

    def embed_query(self, query: str) -> list[float]:
        return self._embed_texts([query], "query")[0]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self._embed_texts(texts, "document")


_embedder: Embedder = GeminiEmbedder()


def set_embedder(embedder: Embedder) -> None:
    """Swap the process-wide embedder (used by tests)."""
    global _embedder
    _embedder = embedder


@functools.lru_cache(maxsize=1)
def default_embedder() -> Embedder:
    return GeminiEmbedder()


def embed_query(query: str) -> list[float]:
    return _embedder.embed_query(query)


def embed_documents(texts: list[str]) -> list[list[float]]:
    return _embedder.embed_documents(texts)
