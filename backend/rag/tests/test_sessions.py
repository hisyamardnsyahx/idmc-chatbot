"""Session store tests against rag.sessions.store (cfg-injected API)."""

from dataclasses import replace

from rag.core import config as config_mod
from rag.sessions import store as sessions


def _cfg(tmp_path):
    base = config_mod.settings
    return replace(
        base,
        storage_dir=tmp_path,
        sessions_dir=tmp_path,
        staging_snapshot=tmp_path / "staging_snapshot.json",
        ingest_report=tmp_path / "ingest_report.json",
        index_meta=tmp_path / "rag_index_meta.json",
    )


def test_session_crud(tmp_path):
    cfg = _cfg(tmp_path)
    s = sessions.create_session(cfg=cfg)
    assert s["id"]
    sessions.append_turn(s["id"], "user", "halo", cfg=cfg)
    sessions.append_turn(s["id"], "assistant", "hai", sources=[], cfg=cfg)
    got = sessions.get_session(s["id"], cfg)
    assert len(got["turns"]) == 2
    assert sessions.history_for_model(got, cfg, limit=10)[0]["text"] == "halo"
    assert any(x["id"] == s["id"] for x in sessions.list_sessions(cfg))
    assert sessions.delete_session(s["id"], cfg) is True
    assert sessions.get_session(s["id"], cfg) is None


def test_session_title_from_first_user_turn(tmp_path):
    cfg = _cfg(tmp_path)
    s = sessions.create_session(cfg=cfg)
    sessions.append_turn(s["id"], "user", "berapa jumlah pegawai?", cfg=cfg)
    got = sessions.get_session(s["id"], cfg)
    assert got["title"] == "berapa jumlah pegawai?"


def test_append_missing_session_raises(tmp_path):
    cfg = _cfg(tmp_path)
    try:
        sessions.append_turn("nope", "user", "halo", cfg=cfg)
    except ValueError:
        return
    raise AssertionError("expected ValueError")


def test_session_rename_and_clear_all(tmp_path):
    cfg = _cfg(tmp_path)
    s1 = sessions.create_session("Initial Title 1", cfg=cfg)
    s2 = sessions.create_session("Initial Title 2", cfg=cfg)
    renamed = sessions.rename_session(s1["id"], "Judul Baru Percakapan", cfg=cfg)
    assert renamed is not None
    assert renamed["title"] == "Judul Baru Percakapan"
    got = sessions.get_session(s1["id"], cfg=cfg)
    assert got["title"] == "Judul Baru Percakapan"
    # rename non-existent returns None
    assert sessions.rename_session("nonexistent", "Title", cfg=cfg) is None
    # clear all
    cleared_count = sessions.clear_all_sessions(cfg=cfg)
    assert cleared_count == 2
    assert len(sessions.list_sessions(cfg=cfg)) == 0


def test_path_traversal_session_lookup_prevented(tmp_path):
    cfg = _cfg(tmp_path)
    traversal_input = "../../../../frontend/package"
    data = sessions.get_session(traversal_input, cfg=cfg)
    assert data is None
    assert sessions.delete_session(traversal_input, cfg=cfg) is False

