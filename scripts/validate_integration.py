"""End-to-end integration smoke test for pipeline -> RAG backend -> API.

This does not call Gemini or any external service:

- the published live handoff bundle is ingested verbatim,
- embeddings are deterministic local vectors,
- the chat model is replaced by a retrieval-grounded stub.

Run from the workspace root:

    py scripts/validate_integration.py

It exercises the real handoff parser, Chroma adapter, retrieval catalogue,
FastAPI routes, CORS, and session persistence.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import shutil
import sys
import tempfile
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from rag.chat import retrieval  # noqa: E402
from rag.chat import service as chat_service  # noqa: E402
from rag.core import config as config_mod  # noqa: E402
from rag.pipeline import embeddings, handoff, vector_store  # noqa: E402
from rag.web import app as app_mod  # noqa: E402
from rag.ingest_from_staging import run_ingest  # noqa: E402

DEFAULT_ARTIFACT = (
    ROOT / "data" / "handoff" / "current" / "ready_for_vector_db_v2.json"
)


class FakeEmbedder:
    """Small deterministic bag-of-token embedding; no network, no API key."""

    dimension = 64

    @classmethod
    def _vector(cls, text: str) -> list[float]:
        vector = [0.0] * cls.dimension
        for token in re.findall(r"[a-z0-9]+", text.lower()):
            digest = hashlib.md5(token.encode("utf-8"), usedforsecurity=False).digest()
            vector[digest[0] % cls.dimension] += 1.0
        norm = math.sqrt(sum(value * value for value in vector))
        if norm == 0.0:
            vector[0] = 1.0
            return vector
        return [value / norm for value in vector]

    def embed_query(self, query: str) -> list[float]:
        return self._vector(query)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._vector(text) for text in texts]


def _use_temp_settings(temp: Path) -> dict[str, object]:
    """Mutate the singleton in place so every module sees the temp paths."""
    original = {
        name: getattr(config_mod.settings, name)
        for name in (
            "storage_dir",
            "chroma_dir",
            "sessions_dir",
            "staging_snapshot",
            "ingest_report",
            "index_meta",
            "collection_name",
        )
    }
    config_mod.settings.storage_dir = temp
    config_mod.settings.chroma_dir = temp / "chroma"
    config_mod.settings.sessions_dir = temp / "sessions"
    config_mod.settings.sessions_dir.mkdir(parents=True, exist_ok=True)
    config_mod.settings.staging_snapshot = temp / "staging_snapshot.json"
    config_mod.settings.ingest_report = temp / "ingest_report.json"
    config_mod.settings.index_meta = temp / "rag_index_meta.json"
    config_mod.settings.collection_name = "rag_e2e_validation"
    vector_store.reset_collection_cache()
    return original


def _restore_settings(original: dict[str, object]) -> None:
    vector_store.reset_collection_cache()
    for name, value in original.items():
        setattr(config_mod.settings, name, value)
    vector_store.reset_collection_cache()


def main() -> int:
    artifact = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_ARTIFACT
    if not artifact.exists():
        print(
            f"Artifact not found: {artifact}\n"
            "Run the live crawl from pipeline/ and copy the published bundle to "
            "data/handoff/current/.",
            file=sys.stderr,
        )
        return 2

    # Validate the manifest before touching the index.
    manifest = artifact.parent / handoff.MANIFEST_NAME
    assert manifest.exists(), f"handoff manifest missing next to {artifact}"
    parsed = handoff.load_handoff(artifact)
    assert parsed.documents, "handoff produced no documents"
    sample_query = " ".join(parsed.documents[0].page_content.split())[:200] or "data"
    assert parsed.catalog and all(
        item.get("dashboard_name") and item.get("slice_name") for item in parsed.catalog
    )

    original_settings = _use_temp_settings(Path(tempfile.mkdtemp(prefix="rag-e2e-")))
    temp_dir = config_mod.settings.storage_dir
    original_embedder = embeddings._embedder
    embeddings.set_embedder(FakeEmbedder())

    try:
        report = run_ingest(artifact, reindex=True)
        assert report["format"] == "v2_chunks", report
        assert report["chunk_count"] == len(parsed.documents)
        assert report["chart_count"] == len(parsed.catalog)
        assert report["index"]["total"] == len(parsed.documents)

        snapshot = json.loads(config_mod.settings.staging_snapshot.read_text(encoding="utf-8"))
        assert snapshot["format"] == "v2_chunks"
        assert snapshot["fingerprint"] == parsed.fingerprint
        assert snapshot["catalog"] == parsed.catalog

        charts = retrieval.list_charts()
        dashboards = retrieval.dashboard_names()
        assert charts and dashboards, (charts, dashboards)

        passages = retrieval.search(sample_query, top_k=3)
        assert passages, "fake-embedding search returned no passages"
        assert all(passage.dashboard and passage.chart for passage in passages)

        # The chat model is stubbed, but everything below it is real: retrieval,
        # session persistence, response formatting, and Pydantic serialization.
        def fake_run_chat(message, history=None, dashboard=None, top_k=5):
            hits = retrieval.search(message or "chart small", top_k=top_k, dashboard_name=dashboard)
            return chat_service.ChatResult(
                "Jawaban validasi dari data pipeline.", hits
            )

        original_run_chat = chat_service.run_chat
        chat_service.run_chat = fake_run_chat
        client = TestClient(app_mod.app)
        try:
            health = client.get("/api/health")
            assert health.status_code == 200 and health.json() == {"status": "ok"}

            stats = client.get("/api/stats")
            assert stats.status_code == 200
            stats_body = stats.json()
            assert stats_body["count"] == len(parsed.documents)
            assert stats_body["charts"] == len(charts)

            catalog = client.get("/api/charts")
            assert catalog.status_code == 200
            assert catalog.json()["charts"] == charts

            chat = client.post(
                "/api/chat",
                json={"message": sample_query, "top_k": 3},
            )
            assert chat.status_code == 200, chat.text
            chat_body = chat.json()
            assert chat_body["session_id"]
            assert chat_body["reply"].startswith("Jawaban validasi")
            assert chat_body["sources"], chat_body
            assert "Sumber:" in chat_body["reply"]
            assert chat_body["sources"][0]["dashboard"]
            assert chat_body["sources"][0]["chart"]

            session_id = chat_body["session_id"]
            sessions = client.get("/api/sessions")
            assert sessions.status_code == 200
            assert any(item["id"] == session_id for item in sessions.json()["sessions"])

            detail = client.get(f"/api/sessions/{session_id}")
            assert detail.status_code == 200
            detail_body = detail.json()
            assert len(detail_body["turns"]) == 2
            assert detail_body["turns"][1]["role"] == "assistant"
            assert detail_body["turns"][1]["sources"], detail_body

            # The alias remains compatible with the old Vite proxy contract.
            alias = client.post(
                "/chat",
                json={"message": sample_query, "session_id": session_id, "top_k": 3},
            )
            assert alias.status_code == 200, alias.text
            assert alias.json()["session_id"] == session_id

            stale = client.post(
                "/api/chat",
                json={"message": "chart small", "session_id": "missing-session"},
            )
            assert stale.status_code == 404

            preflight = client.options(
                "/api/chat",
                headers={
                    "Origin": "http://localhost:5173",
                    "Access-Control-Request-Method": "POST",
                    "Access-Control-Request-Headers": "content-type",
                },
            )
            assert preflight.status_code == 200
            assert preflight.headers["access-control-allow-origin"] == "http://localhost:5173"

            search = client.post("/api/search", json={"query": sample_query, "top_k": 3})
            assert search.status_code == 200
            assert search.json()["results"], search.text
        finally:
            chat_service.run_chat = original_run_chat
    finally:
        embeddings.set_embedder(original_embedder)
        _restore_settings(original_settings)
        shutil.rmtree(temp_dir, ignore_errors=True)

    summary = {
        "artifact": str(artifact),
        "format": report["format"],
        "chunks": report["chunk_count"],
        "charts": report["chart_count"],
        "dashboards": len(dashboards),
        "passages": len(passages),
        "sources": len(chat_body["sources"]),
        "session_turns": len(detail_body["turns"]),
        "checks": [
            "manifest",
            "ingest",
            "chroma",
            "catalog",
            "search",
            "api.chat",
            "api.sessions",
            "api.chat alias",
            "stale session 404",
            "cors",
            "api.search",
        ],
    }
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
