"""Ingest CLI: pipeline handoff -> chunks -> Chroma.

Preferred input is the standalone pipeline's ``ready_for_vector_db_v2.json``.
The backend indexes those whole-row chunks as-is; it never re-chunks them.
Legacy v1 ``staging_superset_data.json`` files still work and are chunked by
the v1 pipeline.

Usage:
    py -m rag.ingest_from_staging --source path/to/ready_for_vector_db_v2.json --reindex
    py -m rag.ingest_from_staging --source path/to/staging_idmc_data.json
    py -m rag.ingest_from_staging --stats
"""

from __future__ import annotations

import argparse
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .core import config as config_mod
from .core.json_io import atomic_write_json, canonical_json, md5_hex, read_json
from .core.logging import setup_logging
from .pipeline import chunking, embeddings, handoff, vector_store

log = logging.getLogger("rag.ingest")


def load_staging_charts(source: Path) -> dict[str, dict[str, Any]]:
    """Load a legacy v1 staging dump (``{"charts": {...}}``)."""
    raw = read_json(source)
    if not isinstance(raw, dict) or not isinstance(raw.get("charts"), dict):
        raise ValueError(f"{source} is not a staging dump with a 'charts' object.")
    charts: dict[str, dict[str, Any]] = {}
    skipped = 0
    for key, rec in raw["charts"].items():
        if not isinstance(rec, dict):
            skipped += 1
            continue
        rows = rec.get("rows") or []
        if not rows:
            skipped += 1
            continue
        charts[str(key)] = {
            "slice_id": rec.get("slice_id", key),
            "slice_name": rec.get("slice_name") or f"Chart {key}",
            "dashboard_uuid": rec.get("dashboard_uuid") or "",
            "dashboard_name": rec.get("dashboard_name") or "Unknown dashboard",
            "colnames": rec.get("colnames") or [],
            "rows": rows,
            "fetched_at": rec.get("fetched_at") or raw.get("extracted_at") or "",
            "stale": bool(rec.get("stale", False)),
        }
    if not charts:
        raise ValueError(f"{source} has no charts with rows.")
    log.info("Loaded %d chart(s) from %s (%d skipped empty)", len(charts), source, skipped)
    return charts


def _catalog_as_charts(catalog: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Keep the legacy retrieval shape available during the transition."""
    charts: dict[str, dict[str, Any]] = {}
    for index, item in enumerate(catalog):
        charts[str(index)] = {
            "slice_id": item.get("slice_id"),
            "slice_name": item.get("slice_name"),
            "dashboard_name": item.get("dashboard_name"),
        }
    return charts


def run_ingest(source: Path | str | None = None, reindex: bool = False) -> dict[str, Any]:
    cfg = config_mod.settings
    resolved = handoff.detect_source(source, default=cfg.default_staging_source)
    parsed = handoff.load_handoff(resolved)

    if parsed.format == "v1_staging":
        charts = load_staging_charts(resolved)
        fingerprint = md5_hex(
            canonical_json({key: charts[key].get("fetched_at") for key in sorted(charts)})
        )
        snapshot: dict[str, Any] = {
            "source": str(resolved),
            "format": "v1_staging",
            "fingerprint": fingerprint,
            "saved_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "chart_count": len(charts),
            "charts": charts,
        }
        documents = chunking.chunk_charts(charts)
        catalog = parsed.catalog
    else:
        documents = parsed.documents or []
        if not documents:
            raise ValueError(f"{resolved} produced no chunks; refusing to publish an empty index.")
        snapshot = {
            "source": str(resolved),
            "format": parsed.format,
            "fingerprint": parsed.fingerprint,
            "saved_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "chart_count": len(parsed.catalog),
            "chunk_count": len(documents),
            "catalog": parsed.catalog,
            # Kept for older readers that still expect a ``charts`` map.
            "charts": _catalog_as_charts(parsed.catalog),
        }
        catalog = parsed.catalog

    atomic_write_json(cfg.staging_snapshot, snapshot, indent=1)

    if reindex:
        log.info("Reindex requested: clearing the existing collection")
        vector_store.reset_collection()

    summary = vector_store.index_documents(documents, embeddings.embed_documents)

    report = {
        "source": str(resolved),
        "format": parsed.format,
        "chart_count": len(catalog),
        "chunk_count": len(documents),
        "avg_chars": round(sum(len(document.page_content) for document in documents) / max(1, len(documents))),
        "index": summary,
        "completed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    atomic_write_json(cfg.ingest_report, report)
    log.info(
        "Ingest done: %d chart(s) -> %d chunk(s) from %s",
        len(catalog),
        len(documents),
        parsed.format,
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="RAG ingest from a pipeline handoff artifact")
    parser.add_argument(
        "--source",
        default=None,
        help="ready_for_vector_db_v2.json, staging_idmc_data.json, legacy staging, or a directory",
    )
    parser.add_argument("--reindex", action="store_true", help="clear the collection before indexing")
    parser.add_argument("--stats", action="store_true", help="print index stats and exit")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    setup_logging(args.verbose)
    if args.stats:
        print(vector_store.get_stats())
        return 0
    try:
        report = run_ingest(args.source, reindex=args.reindex)
    except (FileNotFoundError, ValueError) as exc:
        log.error("Ingest failed: %s", exc)
        return 1
    print(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
