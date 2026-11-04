"""Retrieval tests against rag.chat.retrieval (Passage API)."""

from dataclasses import replace

from rag.chat import retrieval as retrieval_mod
from rag.core import config as config_mod


def _isolated_settings(monkeypatch, tmp_path):
    monkeypatch.setattr(
        config_mod, "settings", replace(config_mod.settings, sessions_dir=tmp_path)
    )


def test_search_shapes_passages(monkeypatch):
    monkeypatch.setattr(
        retrieval_mod.embeddings, "embed_query", lambda q: [0.1, 0.2]
    )
    monkeypatch.setattr(
        retrieval_mod.vector_store,
        "query",
        lambda vector, top_k=5, dashboard_name=None: [
            {
                "content": "Dashboard: D\nChart: C",
                "score": 0.85,
                "metadata": {
                    "dashboard_name": "D",
                    "slice_name": "C",
                    "slice_id": 602,
                    "row_start": 1,
                    "row_end": 3,
                    "total_rows": 14,
                    "extracted_at": "2026-09-29",
                    "stale": False,
                },
            },
        ],
    )
    out = retrieval_mod.search("pegawai", top_k=5)
    assert len(out) == 1
    p = out[0]
    assert p.dashboard == "D"
    assert p.rows_covered == "1-3 of 14"
    assert p.relevance == 0.85
    assert p.possibly_outdated is False


def test_search_rejects_empty(monkeypatch):
    try:
        retrieval_mod.search("   ")
    except ValueError:
        return
    raise AssertionError("expected ValueError")


def test_catalog_reads_v2_snapshot_and_keeps_string_slice_ids(tmp_path, monkeypatch):
    import json

    snapshot = tmp_path / "snapshot.json"
    snapshot.write_text(
        json.dumps(
            {
                "format": "v2_chunks",
                "catalog": [
                    {
                        "slice_id": "608",
                        "slice_name": "Target Belanja",
                        "dashboard_name": "Dashboard Pembangunan",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        config_mod,
        "settings",
        replace(config_mod.settings, staging_snapshot=snapshot),
    )

    assert retrieval_mod.dashboard_names() == ["Dashboard Pembangunan"]
    assert retrieval_mod.list_charts() == [
        {
            "slice_id": "608",
            "slice_name": "Target Belanja",
            "dashboard_name": "Dashboard Pembangunan",
        }
    ]


def test_catalog_falls_back_to_legacy_charts(tmp_path, monkeypatch):
    import json

    snapshot = tmp_path / "snapshot.json"
    snapshot.write_text(
        json.dumps(
            {
                "charts": {
                    "600": {
                        "slice_id": 600,
                        "slice_name": "Jumlah Pegawai",
                        "dashboard_name": "Simpeg",
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        config_mod,
        "settings",
        replace(config_mod.settings, staging_snapshot=snapshot),
    )

    assert retrieval_mod.list_charts()[0]["slice_name"] == "Jumlah Pegawai"
    assert retrieval_mod.dashboard_names() == ["Simpeg"]


def test_search_accepts_v2_string_slice_id(monkeypatch):
    monkeypatch.setattr(
        retrieval_mod.embeddings, "embed_query", lambda q: [0.1, 0.2]
    )
    monkeypatch.setattr(
        retrieval_mod.vector_store,
        "query",
        lambda vector, top_k=5, dashboard_name=None: [
            {
                "content": "chunk",
                "score": 0.75,
                "metadata": {
                    "dashboard_name": "D",
                    "slice_name": "C",
                    "slice_id": "608",
                    "row_start": 1,
                    "row_end": 1,
                    "total_rows": 1,
                    "extracted_at": "2026-10-06",
                    "stale": False,
                },
            }
        ],
    )
    passage = retrieval_mod.search("x")[0]
    assert passage.slice_id == "608"


def test_search_clamps_top_k(monkeypatch):
    seen = {}

    def fake_embed(q):
        return [0.1]

    def fake_query(vector, top_k=5, dashboard_name=None):
        seen["top_k"] = top_k
        return []

    monkeypatch.setattr(retrieval_mod.embeddings, "embed_query", fake_embed)
    monkeypatch.setattr(retrieval_mod.vector_store, "query", fake_query)
    assert retrieval_mod.search("x", top_k=999) == []
    assert seen["top_k"] == config_mod.settings.max_top_k
