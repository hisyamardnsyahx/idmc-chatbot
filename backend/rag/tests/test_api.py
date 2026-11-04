"""Web API tests against rag.web.app with faked service layers."""

from fastapi.testclient import TestClient

from rag.chat import retrieval as retrieval_mod
from rag.chat import service as chat_service
from rag.core.models import Passage
from rag.pipeline import vector_store as store_mod
from rag.web import app as app_mod


def _passage():
    return Passage(
        dashboard="D",
        chart="C",
        slice_id=1,
        rows_covered="1-1 of 1",
        data_as_of="x",
        possibly_outdated=False,
        relevance=0.9,
        content="t",
    )


def _client(tmp_path, monkeypatch):
    from rag.core import config as config_mod

    monkeypatch.setattr(config_mod.settings, "sessions_dir", tmp_path)
    return TestClient(app_mod.app)


def test_health_and_stats(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    assert c.get("/api/health").json() == {"status": "ok"}
    monkeypatch.setattr(
        store_mod,
        "get_stats",
        lambda: {
            "collection": "test",
            "count": 3,
            "embed_model": "m",
            "indexed_at": None,
            "last_summary": {},
        },
    )
    monkeypatch.setattr(retrieval_mod, "list_charts", lambda: [])
    r = c.get("/api/stats")
    assert r.status_code == 200
    assert r.json()["count"] == 3
    assert r.json()["chat_model"]


def test_search_validation(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    r = c.post("/api/search", json={"query": "", "top_k": 5})
    assert r.status_code in (400, 422)
    monkeypatch.setattr(retrieval_mod, "search", lambda q, top_k=5, dashboard_name=None: [_passage()])
    r = c.post("/api/search", json={"query": "pegawai", "top_k": 5})
    assert r.status_code == 200
    assert r.json()["results"][0]["dashboard"] == "D"


def test_chat_flow_formats_and_persists(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    monkeypatch.setattr(
        chat_service, "run_chat", lambda *a, **k: chat_service.ChatResult("Jawaban uji", [_passage()])
    )
    r = c.post("/api/chat", json={"message": "halo"})
    assert r.status_code == 200
    assert r.json()["reply_format"] == "markdown"
    assert "Sumber:" in r.json()["reply"]
    assert len(r.json()["sources"]) == 1
    sid = r.json()["session_id"]
    r2 = c.get(f"/api/sessions/{sid}")
    assert r2.status_code == 200
    assert len(r2.json()["turns"]) == 2
    assert c.delete(f"/api/sessions/{sid}").status_code == 200


def test_chat_alias_accepts_string_slice_id(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    passage = Passage(
        dashboard="D",
        chart="C",
        slice_id="608",
        rows_covered="1-1 of 1",
        data_as_of="2026-10-06",
        possibly_outdated=False,
        relevance=0.9,
        content="t",
    )
    monkeypatch.setattr(
        chat_service,
        "run_chat",
        lambda *a, **k: chat_service.ChatResult("Jawaban uji", [passage]),
    )

    response = c.post("/chat", json={"message": "halo"})

    assert response.status_code == 200
    assert response.json()["sources"][0]["slice_id"] == "608"


def test_cors_preflight_allows_vite_dev_origin(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    response = c.options(
        "/api/chat",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_charts_endpoint_returns_v2_catalog(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    monkeypatch.setattr(
        retrieval_mod,
        "list_charts",
        lambda: [
            {
                "slice_id": "608",
                "slice_name": "Target Belanja",
                "dashboard_name": "Dashboard Pembangunan",
            }
        ],
    )
    monkeypatch.setattr(retrieval_mod, "dashboard_names", lambda: ["Dashboard Pembangunan"])
    response = c.get("/api/charts")
    assert response.status_code == 200
    assert response.json()["charts"][0]["slice_id"] == "608"


def test_chat_rejects_empty(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    assert c.post("/api/chat", json={"message": "  "}).status_code == 400


def test_model_busy_maps_to_503(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)

    def _boom(*a, **k):
        raise chat_service.ModelBusyError("sibuk")

    monkeypatch.setattr(chat_service, "run_chat", _boom)
    r = c.post("/api/chat", json={"message": "halo"})
    assert r.status_code == 503
    assert r.json()["code"] == "model_busy"


def test_quota_exhausted_maps_to_429(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)

    def _boom(*a, **k):
        raise chat_service.QuotaExhaustedError("kuota habis", retry_after_s=24.0)

    monkeypatch.setattr(chat_service, "run_chat", _boom)
    r = c.post("/api/chat", json={"message": "halo"})
    assert r.status_code == 429
    assert r.json()["code"] == "quota_exhausted"
    assert r.json()["retry_after_s"] == 24.0


def test_unreachable_maps_to_502_with_code(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)

    def _boom(*a, **k):
        raise chat_service.UpstreamUnreachableError("putus")

    monkeypatch.setattr(chat_service, "run_chat", _boom)
    r = c.post("/api/chat", json={"message": "halo"})
    assert r.status_code == 502
    assert r.json()["code"] == "upstream_unreachable"


def test_misconfigured_maps_to_500_with_code(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)

    def _boom(*a, **k):
        raise chat_service.ConfigurationError("key salah")

    monkeypatch.setattr(chat_service, "run_chat", _boom)
    r = c.post("/api/chat", json={"message": "halo"})
    assert r.status_code == 500
    assert r.json()["code"] == "server_misconfigured"
