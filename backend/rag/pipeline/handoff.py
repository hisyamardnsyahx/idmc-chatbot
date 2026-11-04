"""Load pipeline handoff artifacts into embedding-ready documents.

The standalone scraping pipeline publishes two useful shapes:

- ``ready_for_vector_db_v2.json`` -- a list of whole-row chunks. This is the
  preferred input: the pipeline already did the chunking, so the backend must
  not chunk it again.
- ``staging_idmc_data.json`` -- schema v2 records. When this is passed, the
  sibling ``ready_for_vector_db_v2.json`` is required.

Legacy v1 ``staging_superset_data.json`` files remain supported by returning
``documents=None``; the caller re-chunks them with the existing v1 pipeline.

All metadata is reduced to Chroma-compatible scalars. Lists and objects are
serialized as deterministic JSON strings rather than dropped.
"""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..core.json_io import canonical_json, md5_hex, read_json
from ..core.models import Document

READY_NAME = "ready_for_vector_db_v2.json"
STAGING_V2_NAME = "staging_idmc_data.json"
STAGING_V1_NAME = "staging_superset_data.json"
MANIFEST_NAME = "handoff_manifest.json"

_REQUIRED_CHUNK_METADATA = (
    "dashboard_name",
    "slice_name",
    "slice_id",
    "row_start",
    "row_end",
    "total_rows",
    "content_hash",
    "stale",
)


@dataclass(frozen=True)
class Handoff:
    """Parsed handoff input.

    ``documents`` is ``None`` only for legacy v1 staging, where the caller owns
    chunking. ``catalog`` is always populated for ``/api/charts`` and the
    dashboard allow-list.
    """

    documents: list[Document] | None
    catalog: list[dict[str, Any]]
    format: str
    fingerprint: str


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def detect_source(source: Path | str | None = None, default: Path | str | None = None) -> Path:
    """Resolve the artifact to ingest, preferring v2 outputs over legacy v1."""
    if source is not None:
        path = Path(source)
        if path.is_dir():
            for name in (READY_NAME, STAGING_V2_NAME, STAGING_V1_NAME):
                candidate = path / name
                if candidate.exists():
                    return candidate
            raise FileNotFoundError(f"No handoff artifact found in {path}")
        if not path.exists():
            raise FileNotFoundError(f"Handoff artifact not found: {path}")
        return path

    base = Path(default).parent if default else Path.cwd()
    for name in (READY_NAME, STAGING_V2_NAME):
        candidate = base / name
        if candidate.exists():
            return candidate
    if default is not None and Path(default).exists():
        return Path(default)
    for name in (READY_NAME, STAGING_V2_NAME, STAGING_V1_NAME):
        candidate = Path.cwd() / name
        if candidate.exists():
            return candidate
    raise FileNotFoundError(
        "No handoff artifact found. Pass --source pointing at "
        f"{READY_NAME} or {STAGING_V2_NAME}."
    )


def load_handoff(source: Path | str) -> Handoff:
    path = detect_source(source)
    raw = read_json(path)
    if raw is None:
        raise ValueError(f"Could not read valid JSON from {path}")

    if isinstance(raw, list):
        documents = _load_chunks(path, raw)
        catalog = _catalog_from_documents(documents)
        return Handoff(
            documents=documents,
            catalog=catalog,
            format="v2_chunks",
            fingerprint=_fingerprint(documents),
        )

    if not isinstance(raw, dict):
        raise ValueError(f"Unsupported handoff shape in {path}")

    if raw.get("schema_version") == 2 and isinstance(raw.get("records"), dict):
        chunks_path = path.parent / READY_NAME
        if not chunks_path.exists():
            raise ValueError(
                f"{STAGING_V2_NAME} is schema v2 but its sibling {READY_NAME} "
                "is missing. Run the pipeline's transformer or pass the chunks "
                "file directly."
            )
        documents = _load_chunks(chunks_path, read_json(chunks_path))
        catalog = _catalog_from_records(raw["records"])
        return Handoff(
            documents=documents,
            catalog=catalog,
            format="v2_staging",
            fingerprint=_fingerprint(documents),
        )

    if isinstance(raw.get("charts"), dict):
        return Handoff(
            documents=None,
            catalog=_catalog_from_charts(raw["charts"]),
            format="v1_staging",
            fingerprint="",
        )

    raise ValueError(
        f"Unsupported handoff shape in {path}: expected a chunk list, "
        "schema_version 2 records, or legacy charts."
    )


def _load_chunks(path: Path, raw: Any) -> list[Document]:
    if not isinstance(raw, list) or not raw:
        raise ValueError(f"{path} must contain a non-empty chunk list")
    _validate_manifest(path, len(raw))

    documents: list[Document] = []
    seen: set[str] = set()
    for index, item in enumerate(raw):
        if not isinstance(item, dict):
            raise ValueError(f"Chunk {index} must be an object")
        chunk_id = item.get("id")
        content = item.get("page_content")
        metadata = item.get("metadata")
        if not isinstance(chunk_id, str) or not chunk_id.strip():
            raise ValueError(f"Chunk {index} has no usable id")
        if chunk_id in seen:
            raise ValueError(f"Duplicate chunk id: {chunk_id}")
        seen.add(chunk_id)
        if not isinstance(content, str) or not content.strip():
            raise ValueError(f"Chunk {chunk_id} has empty page_content")
        if not isinstance(metadata, dict):
            raise ValueError(f"Chunk {chunk_id} has no metadata object")

        normalized = _normalize_chunk_metadata(chunk_id, metadata)
        documents.append(
            Document(id=chunk_id, page_content=content, metadata=normalized)
        )
    return documents


def _normalize_chunk_metadata(chunk_id: str, metadata: dict[str, Any]) -> dict[str, Any]:
    source = dict(metadata)
    # Accept the pipeline's chart_name/chart_id aliases as well as the
    # retrieval-facing slice_name/slice_id names.
    if "slice_name" not in source and "chart_name" in source:
        source["slice_name"] = source["chart_name"]
    if "slice_id" not in source and "chart_id" in source:
        source["slice_id"] = source["chart_id"]

    missing = [name for name in _REQUIRED_CHUNK_METADATA if name not in source]
    if missing:
        raise ValueError(
            f"Chunk {chunk_id} is missing required metadata: {', '.join(missing)}"
        )

    for name in ("dashboard_name", "slice_name", "content_hash"):
        if not isinstance(source[name], str) or not source[name].strip():
            raise ValueError(f"Chunk {chunk_id} has invalid {name}")
    if not isinstance(source["slice_id"], (str, int)) or isinstance(source["slice_id"], bool):
        raise ValueError(f"Chunk {chunk_id} has invalid slice_id")
    for name in ("row_start", "row_end", "total_rows"):
        if type(source[name]) is not int or source[name] < 0:
            raise ValueError(f"Chunk {chunk_id} has invalid {name}")
    if type(source["stale"]) is not bool:
        raise ValueError(f"Chunk {chunk_id} has invalid stale")
    if source["row_start"] > source["row_end"] or source["row_end"] > source["total_rows"]:
        raise ValueError(f"Chunk {chunk_id} has an invalid row range")

    normalized: dict[str, Any] = {}
    for key, value in source.items():
        if value is None:
            continue
        if not isinstance(key, str):
            raise ValueError(f"Chunk {chunk_id} has a non-string metadata key")
        normalized[key] = _scalar_value(chunk_id, key, value)

    normalized.setdefault("extracted_at", "")
    normalized.setdefault("data_as_of", normalized.get("last_successful_fetch_at", ""))
    return normalized


def _scalar_value(chunk_id: str, key: str, value: Any) -> str | int | float | bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(f"Chunk {chunk_id} metadata {key} is not finite")
        return value
    if isinstance(value, str):
        return value
    return canonical_json(value)


def _validate_manifest(path: Path, chunk_count: int) -> None:
    manifest_path = path.parent / MANIFEST_NAME
    if not manifest_path.exists():
        return
    manifest = read_json(manifest_path)
    if not isinstance(manifest, dict):
        raise ValueError(
            f"Invalid handoff manifest: {manifest_path.name} is not a JSON object"
        )
    if manifest.get("schema_version") not in (None, 2):
        raise ValueError(f"Unsupported handoff manifest schema: {manifest.get('schema_version')}")
    expected_count = manifest.get("chunk_count")
    if type(expected_count) is not int:
        raise ValueError("Handoff manifest has no integer chunk_count")
    if expected_count != chunk_count:
        raise ValueError(
            f"Handoff manifest chunk_count={expected_count} does not match "
            f"{chunk_count} chunks in {path.name}"
        )
    files = manifest.get("files")
    entry = files.get(path.name) if isinstance(files, dict) else None
    if not isinstance(entry, dict):
        raise ValueError(f"Handoff manifest does not describe {path.name}")
    expected_hash = entry.get("sha256")
    if not isinstance(expected_hash, str) or not expected_hash:
        raise ValueError(f"Handoff manifest has no sha256 for {path.name}")
    actual = sha256_file(path)
    if actual != expected_hash:
        raise ValueError(f"Handoff checksum mismatch for {path.name}")
    expected_bytes = entry.get("bytes")
    if type(expected_bytes) is not int:
        raise ValueError(f"Handoff manifest has no byte size for {path.name}")
    if expected_bytes != path.stat().st_size:
        raise ValueError(f"Handoff size mismatch for {path.name}")


def _catalog_from_documents(documents: list[Document]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str, str]] = set()
    catalog: list[dict[str, Any]] = []
    for document in documents:
        metadata = document.metadata
        item = {
            "slice_id": metadata.get("slice_id"),
            "slice_name": metadata.get("slice_name"),
            "dashboard_name": metadata.get("dashboard_name"),
        }
        key = (str(item["dashboard_name"]), str(item["slice_name"]), str(item["slice_id"]))
        if key in seen:
            continue
        seen.add(key)
        catalog.append(item)
    return sorted(catalog, key=lambda item: (
        str(item["dashboard_name"]).casefold(),
        str(item["slice_name"]).casefold(),
        str(item["slice_id"]),
    ))


def _catalog_from_records(records: dict[str, Any]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str, str]] = set()
    catalog: list[dict[str, Any]] = []
    for key in sorted(records):
        record = records[key]
        if not isinstance(record, dict):
            raise ValueError(f"Record {key} must be an object")
        metadata = record.get("metadata")
        if not isinstance(metadata, dict):
            raise ValueError(f"Record {key} has no metadata object")
        item = {
            "slice_id": metadata.get("slice_id", record.get("chart_id")),
            "slice_name": metadata.get("chart_name") or metadata.get("slice_name"),
            "dashboard_name": metadata.get("dashboard_name"),
        }
        if item["slice_id"] is None or not item["slice_name"] or not item["dashboard_name"]:
            raise ValueError(f"Record {key} has incomplete catalog metadata")
        identity = (str(item["dashboard_name"]), str(item["slice_name"]), str(item["slice_id"]))
        if identity in seen:
            continue
        seen.add(identity)
        catalog.append(item)
    return sorted(catalog, key=lambda item: (
        str(item["dashboard_name"]).casefold(),
        str(item["slice_name"]).casefold(),
        str(item["slice_id"]),
    ))


def _catalog_from_charts(charts: dict[str, Any]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str, str]] = set()
    catalog: list[dict[str, Any]] = []
    for key in sorted(charts, key=str):
        chart = charts[key]
        if not isinstance(chart, dict):
            continue
        item = {
            "slice_id": chart.get("slice_id", key),
            "slice_name": chart.get("slice_name") or f"Chart {key}",
            "dashboard_name": chart.get("dashboard_name") or "Unknown dashboard",
        }
        identity = (str(item["dashboard_name"]), str(item["slice_name"]), str(item["slice_id"]))
        if identity in seen:
            continue
        seen.add(identity)
        catalog.append(item)
    return sorted(catalog, key=lambda item: (
        str(item["dashboard_name"]).casefold(),
        str(item["slice_name"]).casefold(),
        str(item["slice_id"]),
    ))


def _fingerprint(documents: list[Document]) -> str:
    return md5_hex(
        canonical_json(
            [
                {"id": document.id, "content_hash": document.metadata["content_hash"]}
                for document in documents
            ]
        )
    )
