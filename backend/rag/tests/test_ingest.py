"""Ingest loader tests: staging shape validation and snapshot writing."""

from dataclasses import replace

from rag import ingest_from_staging as ingest_mod
from rag.core import config as config_mod


def _staging(path, charts):
    import json

    path.write_text(json.dumps({"charts": charts}), encoding="utf-8")
    return path


def _chart(slice_id=602):
    return {
        "slice_id": slice_id,
        "slice_name": "Pendidikan",
        "dashboard_name": "Simpeg",
        "dashboard_uuid": "u",
        "colnames": ["tingkat_pendidikan"],
        "rows": [{"tingkat_pendidikan": "SD"}],
        "fetched_at": "2026-09-29",
        "stale": False,
    }


def test_rejects_non_staging_file(tmp_path):
    p = _staging(tmp_path / "bad.json", [])
    try:
        ingest_mod.load_staging_charts(p)
    except ValueError:
        return
    raise AssertionError("expected ValueError")


def test_skips_empty_charts(tmp_path):
    p = _staging(tmp_path / "s.json", {"1": {**_chart(1), "rows": []}, "2": _chart(2)})
    charts = ingest_mod.load_staging_charts(p)
    assert list(charts) == ["2"]


def test_run_ingest_writes_snapshot_and_report(tmp_path, monkeypatch):
    src = _staging(tmp_path / "staging.json", {"602": _chart()})
    monkeypatch.setattr(
        config_mod,
        "settings",
        replace(
            config_mod.settings,
            sessions_dir=tmp_path,
            staging_snapshot=tmp_path / "staging_snapshot.json",
            ingest_report=tmp_path / "ingest_report.json",
            index_meta=tmp_path / "rag_index_meta.json",
        ),
    )
    monkeypatch.setattr(
        ingest_mod.vector_store,
        "index_documents",
        lambda docs, fn: {"embedded": len(docs), "metadata_only": 0, "deleted": 0, "total": len(docs)},
    )
    report = ingest_mod.run_ingest(src)
    assert report["chart_count"] == 1
    assert report["chunk_count"] == 1
    assert (tmp_path / "staging_snapshot.json").exists()
    assert (tmp_path / "ingest_report.json").exists()
