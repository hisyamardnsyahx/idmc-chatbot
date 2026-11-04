"""Chroma adapter: index, query, and stats over embedding-ready documents."""

from __future__ import annotations

import functools
import logging
from datetime import datetime, timezone
from typing import Any

from ..core import config as config_mod
from ..core.json_io import atomic_write_json, read_json
from ..core.models import Document

log = logging.getLogger("rag.pipeline.store")


@functools.lru_cache(maxsize=1)
def get_collection():
    import chromadb

    config_mod.settings.chroma_dir.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(config_mod.settings.chroma_dir))
    return client.get_or_create_collection(
        config_mod.settings.collection_name, metadata={"hnsw:space": "cosine"}
    )


def reset_collection_cache() -> None:
    get_collection.cache_clear()


def reset_collection() -> int:
    """Delete every vector in the active collection and return the old count.

    ``--reindex`` uses this so removed or renamed chunks cannot survive a
    pipeline handoff. Metadata-only refresh is still the default for ordinary
    ingest runs.
    """
    collection = get_collection()
    existing = collection.get(include=[])
    ids = existing.get("ids") or []
    if ids:
        collection.delete(ids=ids)
    log.info("Cleared %d vector(s) from %s", len(ids), config_mod.settings.collection_name)
    return len(ids)


def index_documents(docs: list[Document], embed_documents_fn) -> dict[str, int]:
    """Sync the collection to ``docs``.

    Only chunks whose ``content_hash`` changed are re-embedded; the rest get
    a metadata refresh. ``embed_documents_fn`` is injected so tests can pass
    a fake instead of calling Gemini.
    """
    col = get_collection()
    new_ids = {d.id for d in docs}

    existing = col.get(include=["metadatas"])
    existing_hash = {
        doc_id: (meta or {}).get("content_hash")
        for doc_id, meta in zip(existing["ids"], existing["metadatas"])
    }

    stale_ids = [i for i in existing_hash if i not in new_ids]
    if stale_ids:
        col.delete(ids=stale_ids)

    changed = [d for d in docs if existing_hash.get(d.id) != d.metadata["content_hash"]]
    unchanged = [d for d in docs if existing_hash.get(d.id) == d.metadata["content_hash"]]

    if unchanged:
        col.update(ids=[d.id for d in unchanged], metadatas=[d.metadata for d in unchanged])

    for i in range(0, len(changed), config_mod.settings.embed_batch):
        batch = changed[i : i + config_mod.settings.embed_batch]
        vectors = embed_documents_fn([d.page_content for d in batch])
        col.upsert(
            ids=[d.id for d in batch],
            documents=[d.page_content for d in batch],
            metadatas=[d.metadata for d in batch],
            embeddings=vectors,
        )
        log.info(
            "Embedded %d/%d chunk(s)", min(i + config_mod.settings.embed_batch, len(changed)), len(changed)
        )

    summary = {
        "embedded": len(changed),
        "metadata_only": len(unchanged),
        "deleted": len(stale_ids),
        "total": col.count(),
    }
    atomic_write_json(
        config_mod.settings.index_meta,
        {
            **summary,
            "collection": config_mod.settings.collection_name,
            "embed_model": config_mod.settings.embed_model,
            "indexed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        },
    )
    log.info("Vector index synced: %s", summary)
    return summary


def query(
    vector: list[float], top_k: int = 5, dashboard_name: str | None = None
) -> list[dict[str, Any]]:
    res = get_collection().query(
        query_embeddings=[vector],
        n_results=top_k,
        where={"dashboard_name": dashboard_name} if dashboard_name else None,
        include=["documents", "metadatas", "distances"],
    )
    hits: list[dict[str, Any]] = []
    docs = (res.get("documents") or [[]])[0]
    metas = (res.get("metadatas") or [[]])[0]
    dists = (res.get("distances") or [[]])[0]
    for doc, meta, dist in zip(docs, metas, dists):
        score = 1.0 - float(dist)
        if score >= config_mod.settings.min_score:
            hits.append({"content": doc, "metadata": meta or {}, "score": score})
    return hits


def get_stats() -> dict[str, Any]:
    meta = read_json(config_mod.settings.index_meta, default={}) or {}
    try:
        count = get_collection().count()
    except Exception:
        count = meta.get("total", 0)
    return {
        "collection": config_mod.settings.collection_name,
        "count": count,
        "embed_model": config_mod.settings.embed_model,
        "indexed_at": meta.get("indexed_at"),
        "last_summary": {
            k: meta.get(k) for k in ("embedded", "metadata_only", "deleted", "total")
        },
    }
