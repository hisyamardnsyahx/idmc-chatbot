"""Deterministic manifest for the pipeline -> backend handoff.

The pipeline owns extraction, chunking and publication. This manifest lets a
consumer verify that the bundle it is about to index is the complete, intended
publication. It intentionally contains no RAG, embedding or vector-store code.
"""
from __future__ import annotations

import hashlib
import json

from contracts import NORMALIZATION_VERSION, SCHEMA_VERSION
from etl_common import TRANSFORM_VERSION
from contracts import utcnow

MANIFEST_NAME = "handoff_manifest.json"
READY_NAME = "ready_for_vector_db_v2.json"
STAGING_NAME = "staging_idmc_data.json"


def serialize_payload(value):
    """Match ``etl_common.atomic_write_json`` byte-for-byte."""
    return json.dumps(
        value, sort_keys=True, ensure_ascii=False, allow_nan=False, indent=2
    ) + "\n"


def build_manifest(payloads, report=None):
    """Build a manifest describing every payload except the manifest itself."""
    report = report or {}
    files = {}
    for name in sorted(payloads):
        encoded = serialize_payload(payloads[name]).encode("utf-8")
        files[name] = {
            "sha256": hashlib.sha256(encoded).hexdigest(),
            "bytes": len(encoded),
        }

    documents = payloads.get(READY_NAME) or []
    staging = payloads.get(STAGING_NAME) or {}
    records = staging.get("records") if isinstance(staging, dict) else {}
    record_count = report.get("records_produced")
    if not isinstance(record_count, int):
        record_count = len(records) if isinstance(records, dict) else 0

    return {
        "schema_version": SCHEMA_VERSION,
        "normalization_version": NORMALIZATION_VERSION,
        "transform_version": TRANSFORM_VERSION,
        "published_at": report.get("started_at") or utcnow(),
        "status": report.get("status", "ok"),
        "record_count": record_count,
        "chunk_count": len(documents),
        "files": files,
    }
