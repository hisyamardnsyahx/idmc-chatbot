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
