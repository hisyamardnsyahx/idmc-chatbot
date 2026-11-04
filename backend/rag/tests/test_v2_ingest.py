"""V2 pipeline handoff ingestion tests.

These tests pin the contract between ``ready_for_vector_db_v2.json`` and the
backend index. The pipeline owns chunking; the backend must never rechunk it.
"""

import json
from dataclasses import replace

import pytest

from rag import ingest_from_staging as ingest_mod
from rag.core import config as config_mod
from rag.pipeline import handoff as handoff_mod


def _chunk(
    *,
    chunk_id="v2-record-chunk0",
    dashboard="Dashboard Koperasi",
    chart="Jumlah Koperasi",
    slice_id="608",
    metadata_extra=None,
):
    metadata = {
        "dashboard_name": dashboard,
        "slice_name": chart,
        "slice_id": slice_id,
        "row_start": 1,
        "row_end": 2,
        "total_rows": 5,
        "chunk_index": 0,
        "chunk_count": 2,
        "content_hash": "abc123",
        "extracted_at": "2026-10-06T04:36:00+00:00",
        "stale": False,
        "columns": ["wilayah", "jumlah"],
        "effective_filters": [],
    }
    if metadata_extra:
        metadata.update(metadata_extra)
    return {
        "id": chunk_id,
        "page_content": "Dashboard: Dashboard Koperasi\nChart: Jumlah Koperasi\n\n- wilayah: DIY | jumlah: 42",
        "metadata": metadata,
    }


def _write(path, value):
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def test_loads_v2_chunk_list_and_sanitizes_metadata(tmp_path):
    path = _write(tmp_path / "ready_for_vector_db_v2.json", [_chunk()])

    result = handoff_mod.load_handoff(path)

    assert result.format == "v2_chunks"
    assert len(result.documents) == 1
    document = result.documents[0]
    assert document.id == "v2-record-chunk0"
    assert document.metadata["slice_id"] == "608"
    assert document.metadata["dashboard_name"] == "Dashboard Koperasi"
    # Lists are serialized because Chroma metadata must be scalar.
    assert document.metadata["columns"] == '["wilayah","jumlah"]'
    assert "effective_filters" in document.metadata
    assert result.catalog == [
        {
            "slice_id": "608",
            "slice_name": "Jumlah Koperasi",
            "dashboard_name": "Dashboard Koperasi",
        }
    ]


def test_loads_v2_staging_with_sibling_chunks(tmp_path):
    record = {
        "record_id": "superset:dashboard:608:result0",
        "target_id": "superset:dashboard:608",
        "source_type": "superset",
        "dashboard_id": "dashboard",
        "chart_id": "608",
        "result_index": 0,
        "raw_rows": [{"wilayah": "DIY", "jumlah": 42}],
        "metadata": {
            "source_name": "Superset",
            "dashboard_name": "Dashboard Koperasi",
            "chart_name": "Jumlah Koperasi",
            "slice_name": "Jumlah Koperasi",
            "slice_id": "608",
            "source_url": "https://example.test/chart",
            "statistical_period": None,
            "effective_filters": [],
            "source_update_date": None,
            "unit": None,
            "last_checked_at": "2026-10-06T04:36:00+00:00",
            "last_successful_fetch_at": "2026-10-06T04:36:00+00:00",
            "stale": False,
            "is_complete": "unknown",
            "extraction_mode": "api",
        },
    }
    staging = _write(
        tmp_path / "staging_idmc_data.json",
        {
            "schema_version": 2,
            "normalization_version": "2.1.0",
            "records": {record["record_id"]: record},
        },
    )
    _write(tmp_path / "ready_for_vector_db_v2.json", [_chunk()])

    result = handoff_mod.load_handoff(staging)

    assert result.format == "v2_staging"
    assert len(result.documents) == 1
    assert result.catalog[0]["slice_id"] == "608"


def test_v2_staging_without_chunks_fails_with_actionable_error(tmp_path):
    staging = _write(
        tmp_path / "staging_idmc_data.json",
        {"schema_version": 2, "records": {}},
    )

    with pytest.raises(ValueError, match="ready_for_vector_db_v2.json"):
        handoff_mod.load_handoff(staging)


def test_manifest_chunk_count_mismatch_is_rejected(tmp_path):
    path = _write(tmp_path / "ready_for_vector_db_v2.json", [_chunk()])
    _write(
        tmp_path / "handoff_manifest.json",
        {
            "schema_version": 2,
            "chunk_count": 99,
            "record_count": 1,
            "files": {
                "ready_for_vector_db_v2.json": {
                    "sha256": handoff_mod.sha256_file(path),
                    "bytes": path.stat().st_size,
                }
            },
        },
    )

    with pytest.raises(ValueError, match="chunk_count"):
        handoff_mod.load_handoff(path)


def _write_manifest(tmp_path, path, *, sha256=None, size=None):
    _write(
        tmp_path / "handoff_manifest.json",
        {
            "schema_version": 2,
            "chunk_count": 1,
            "files": {
                path.name: {
                    "sha256": sha256 or handoff_mod.sha256_file(path),
                    "bytes": path.stat().st_size if size is None else size,
                }
            },
        },
    )


def test_manifest_checksum_mismatch_is_rejected(tmp_path):
    path = _write(tmp_path / "ready_for_vector_db_v2.json", [_chunk()])
    _write_manifest(tmp_path, path, sha256="0" * 64)

    with pytest.raises(ValueError, match="checksum"):
        handoff_mod.load_handoff(path)


def test_manifest_size_mismatch_is_rejected(tmp_path):
    path = _write(tmp_path / "ready_for_vector_db_v2.json", [_chunk()])
    _write_manifest(tmp_path, path, size=path.stat().st_size + 1)

    with pytest.raises(ValueError, match="size"):
        handoff_mod.load_handoff(path)


def test_manifest_without_chunk_file_entry_is_rejected(tmp_path):
    path = _write(tmp_path / "ready_for_vector_db_v2.json", [_chunk()])
    _write(
        tmp_path / "handoff_manifest.json",
        {"schema_version": 2, "chunk_count": 1, "files": {}},
    )

    with pytest.raises(ValueError, match="does not describe"):
        handoff_mod.load_handoff(path)


def test_corrupt_manifest_is_rejected(tmp_path):
    path = _write(tmp_path / "ready_for_vector_db_v2.json", [_chunk()])
    (tmp_path / "handoff_manifest.json").write_text("{not json", encoding="utf-8")

    with pytest.raises(ValueError, match="Invalid handoff manifest"):
        handoff_mod.load_handoff(path)


def test_chunk_missing_required_metadata_is_rejected(tmp_path):
    broken = _chunk()
    del broken["metadata"]["content_hash"]
    path = _write(tmp_path / "ready_for_vector_db_v2.json", [broken])

    with pytest.raises(ValueError, match="content_hash"):
        handoff_mod.load_handoff(path)


def test_duplicate_chunk_ids_are_rejected(tmp_path):
    first = _chunk()
    second = _chunk()
    second["page_content"] = "different"
    path = _write(tmp_path / "ready_for_vector_db_v2.json", [first, second])

    with pytest.raises(ValueError, match="(?i)duplicate"):
        handoff_mod.load_handoff(path)


def test_run_ingest_v2_writes_catalog_snapshot(tmp_path, monkeypatch):
    source = _write(tmp_path / "ready_for_vector_db_v2.json", [_chunk()])
    monkeypatch.setattr(
        config_mod,
        "settings",
        replace(
            config_mod.settings,
            staging_snapshot=tmp_path / "staging_snapshot.json",
            ingest_report=tmp_path / "ingest_report.json",
            index_meta=tmp_path / "rag_index_meta.json",
        ),
    )
    monkeypatch.setattr(
        ingest_mod.vector_store,
        "index_documents",
        lambda docs, fn: {
            "embedded": len(docs),
            "metadata_only": 0,
            "deleted": 0,
            "total": len(docs),
        },
    )

    report = ingest_mod.run_ingest(source)

    snapshot = json.loads((tmp_path / "staging_snapshot.json").read_text(encoding="utf-8"))
    assert snapshot["format"] == "v2_chunks"
    assert snapshot["catalog"] == [
        {
            "slice_id": "608",
            "slice_name": "Jumlah Koperasi",
            "dashboard_name": "Dashboard Koperasi",
        }
    ]
    assert report["format"] == "v2_chunks"
    assert report["chunk_count"] == 1
    assert report["chart_count"] == 1
