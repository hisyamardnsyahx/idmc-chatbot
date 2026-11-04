"""Chunking tests against rag.pipeline.chunking (Document API)."""

from rag.pipeline import chunking as chunk_mod


def _chart(n=5):
    return {
        "slice_id": 602,
        "slice_name": "Pendidikan",
        "dashboard_name": "Simpeg",
        "dashboard_uuid": "u",
        "colnames": ["tingkat_pendidikan", "Jumlah Pegawai"],
        "rows": [
            {"tingkat_pendidikan": f"Jenjang {i}", "Jumlah Pegawai": float(i)}
            for i in range(n)
        ],
        "fetched_at": "2026-09-29T00:00:00+00:00",
        "stale": False,
    }


def test_chunk_single_group_has_header():
    docs = chunk_mod.chunk_chart(_chart(3), max_chars=5000)
    assert len(docs) == 1
    assert docs[0].id == "slice602-chunk0"
    assert "Dashboard: Simpeg" in docs[0].page_content
    assert docs[0].metadata["slice_id"] == 602
    assert set(docs[0].metadata) >= {"dashboard_name", "content_hash", "row_start"}


def test_chunk_splits_and_ids_deterministic():
    docs = chunk_mod.chunk_chart(_chart(30), max_chars=400)
    assert len(docs) > 1
    assert [d.id for d in docs] == [f"slice602-chunk{i}" for i in range(len(docs))]
    again = chunk_mod.chunk_chart(_chart(30), max_chars=400)
    assert docs[0].metadata["content_hash"] == again[0].metadata["content_hash"]


def test_chunk_skips_empty():
    assert chunk_mod.chunk_chart(_chart(0)) == []


def test_chunk_bulk_counts_groups():
    charts = {"602": _chart(3), "603": {**_chart(30), "slice_id": 603}}
    docs = chunk_mod.chunk_charts(charts)
    assert len([d for d in docs if d.id.startswith("slice602-")]) == 1
    assert len([d for d in docs if d.id.startswith("slice603-")]) > 1
