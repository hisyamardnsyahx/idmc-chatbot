"""HTTP routes for the RAG web chatbot.

Thin by design: every route delegates to :mod:`rag.chat` (LLM loop),
:mod:`rag.sessions` (conversation state), or :mod:`rag.pipeline`
(retrieval/index), then shapes the result with :mod:`rag.web.schemas`.
No prompt text, retry logic, or chunking lives here.
"""

from __future__ import annotations

import logging
import os
import re
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from ..chat import response as response_fmt
from ..chat import retrieval, service as chat_service
from ..core import config as config_mod
from ..core.errors import (
    ChatError,
    ConfigurationError,
    ModelBusyError,
    ModelEmptyError,
    QuotaExhaustedError,
    ToolLoopExhaustedError,
    UpstreamUnreachableError,
)
from ..pipeline import vector_store
from ..sessions import store as session_store
from . import schemas

log = logging.getLogger("rag.web")
BASE_DIR = Path(__file__).resolve().parent.parent

app = FastAPI(title="RAG Web Chatbot")

# The Vite dev server proxies /api, but a separately hosted frontend needs CORS.
if config_mod.settings.cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(config_mod.settings.cors_origins),
        allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type"],
        max_age=600,
    )

if (BASE_DIR / "static").exists():
    app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")


@app.exception_handler(ModelBusyError)
async def _busy_handler(_: Request, exc: ModelBusyError) -> JSONResponse:
    return JSONResponse(status_code=503, content={"detail": str(exc), "code": "model_busy"})


@app.exception_handler(QuotaExhaustedError)
async def _quota_handler(_: Request, exc: QuotaExhaustedError) -> JSONResponse:
    body: dict[str, object] = {"detail": str(exc), "code": "quota_exhausted"}
    if exc.retry_after_s is not None:
        body["retry_after_s"] = exc.retry_after_s
    return JSONResponse(content=body, status_code=429)


@app.exception_handler(UpstreamUnreachableError)
async def _unreachable_handler(_: Request, exc: UpstreamUnreachableError) -> JSONResponse:
    return JSONResponse(status_code=502, content={"detail": str(exc), "code": "upstream_unreachable"})


@app.exception_handler(ConfigurationError)
async def _config_handler(_: Request, exc: ConfigurationError) -> JSONResponse:
    return JSONResponse(status_code=500, content={"detail": str(exc), "code": "server_misconfigured"})


@app.exception_handler(ModelEmptyError)
async def _empty_handler(_: Request, exc: ModelEmptyError) -> JSONResponse:
    return JSONResponse(status_code=502, content={"detail": str(exc), "code": "model_empty"})


@app.exception_handler(ToolLoopExhaustedError)
async def _loop_handler(_: Request, exc: ToolLoopExhaustedError) -> JSONResponse:
    return JSONResponse(status_code=502, content={"detail": str(exc), "code": "tool_loop"})


@app.exception_handler(ChatError)
async def _chat_handler(_: Request, exc: ChatError) -> JSONResponse:
    return JSONResponse(status_code=500, content={"detail": str(exc), "code": "chat_failed"})


def _passage_to_source(p) -> schemas.Source:
    return schemas.Source(
        dashboard=p.dashboard,
        chart=p.chart,
        slice_id=p.slice_id,
        rows_covered=p.rows_covered,
        data_as_of=p.data_as_of,
        possibly_outdated=p.possibly_outdated,
        relevance=p.relevance,
        content=p.content,
        source_url=getattr(p, "source_url", "") or "https://idmc.jogjaprov.go.id/",
    )


@app.get("/", response_class=HTMLResponse)
def index() -> HTMLResponse:
    html_path = BASE_DIR / "templates" / "index.html"
    if not html_path.exists():
        return HTMLResponse("<h1>RAG API is running. Frontend not built yet.</h1>")
    return HTMLResponse(html_path.read_text(encoding="utf-8"))


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/health")
def health_root() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/stats", response_model=schemas.StatsResponse)
def stats() -> schemas.StatsResponse:
    from ..core.config import chat_models

    s = vector_store.get_stats()
    charts = retrieval.list_charts()
    models = chat_models(config_mod.settings)
    return schemas.StatsResponse(
        collection=s["collection"],
        count=s["count"],
        embed_model=s["embed_model"],
        chat_provider=config_mod.settings.chat_provider,
        chat_model=models[0] if models else "",
        indexed_at=s.get("indexed_at"),
        last_summary=s.get("last_summary") or {},
        charts=len(charts),
        sessions=len(session_store.list_sessions()),
    )


@app.get("/api/charts")
def charts() -> dict[str, Any]:
    return {"charts": retrieval.list_charts(), "dashboards": retrieval.dashboard_names()}


@app.post("/api/search", response_model=schemas.SearchResponse)
def api_search(req: schemas.SearchRequest) -> schemas.SearchResponse:
    # ChatError subclasses propagate to the dedicated handlers above.
    try:
        passages = retrieval.search(
            req.query, top_k=req.top_k, dashboard_name=req.dashboard_name
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ChatError:
        raise
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    return schemas.SearchResponse(results=[_passage_to_source(p) for p in passages])


@app.post("/api/chat", response_model=schemas.ChatResponse)
@app.post("/chat", response_model=schemas.ChatResponse, include_in_schema=False)
def api_chat(req: schemas.ChatRequest) -> schemas.ChatResponse:
    message = (req.message or "").strip()
    if not message:
        raise HTTPException(status_code=400, detail="'message' is required.")
    if req.session_id:
        session = session_store.get_session(req.session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="session not found")
    else:
        session = session_store.create_session()
    history = session_store.history_for_model(session)
    try:
        result = chat_service.run_chat(
            message, history, dashboard=req.dashboard_name, top_k=req.top_k
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ChatError:
        raise
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    formatted = response_fmt.format_reply(result.text, result.passages)
    sources = [_passage_to_source(p) for p in result.passages]
    session_store.append_turn(session["id"], "user", message)
    session_store.append_turn(
        session["id"], "assistant", formatted.text, sources=[s.model_dump() for s in sources]
    )
    log.info("chat answered: session=%s passages=%d", session["id"], len(sources))
    return schemas.ChatResponse(
        session_id=session["id"],
        reply=formatted.text,
        reply_format="markdown",
        sources=sources,
    )


@app.get("/api/sessions")
def api_list_sessions(request: Request) -> dict[str, Any]:
    expected_token = os.environ.get("SESSION_AUTH_TOKEN", "").strip()
    if expected_token:
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer ") or auth_header[7:].strip() != expected_token:
            raise HTTPException(status_code=401, detail="Unauthorized")
    return {"sessions": session_store.list_sessions()}


@app.get("/api/sessions/{session_id}", response_model=schemas.SessionDetail)
def api_get_session(session_id: str) -> schemas.SessionDetail:
    if not re.match(r"^[a-zA-Z0-9_-]{1,64}$", session_id):
        raise HTTPException(status_code=400, detail="Invalid session ID format")
    s = session_store.get_session(session_id)
    if s is None:
        raise HTTPException(status_code=404, detail="session not found")
    turns = [
        schemas.Turn(
            role=t.get("role", ""),
            text=t.get("text", ""),
            sources=[schemas.Source(**x) for x in (t.get("sources") or [])],
            at=t.get("at", ""),
        )
        for t in (s.get("turns") or [])
    ]
    return schemas.SessionDetail(
        id=s.get("id", session_id),
        title=s.get("title", "Chat"),
        created_at=s.get("created_at", ""),
        updated_at=s.get("updated_at", ""),
        turns=turns,
    )


@app.delete("/api/sessions/{session_id}")
def api_delete_session(session_id: str) -> dict[str, Any]:
    if not re.match(r"^[a-zA-Z0-9_-]{1,64}$", session_id):
        raise HTTPException(status_code=400, detail="Invalid session ID format")
    ok = session_store.delete_session(session_id)
    if not ok:
        raise HTTPException(status_code=404, detail="session not found")
    return {"deleted": session_id}


@app.patch("/api/sessions/{session_id}")
def api_rename_session(session_id: str, req: schemas.SessionRenameRequest) -> dict[str, Any]:
    if not re.match(r"^[a-zA-Z0-9_-]{1,64}$", session_id):
        raise HTTPException(status_code=400, detail="Invalid session ID format")
    new_title = req.title.strip()
    if not new_title:
        raise HTTPException(status_code=400, detail="Title cannot be empty")
    s = session_store.rename_session(session_id, new_title)
    if s is None:
        raise HTTPException(status_code=404, detail="session not found")
    return {"id": session_id, "title": s["title"], "updated_at": s["updated_at"]}


@app.delete("/api/sessions")
def api_clear_all_sessions() -> dict[str, Any]:
    count = session_store.clear_all_sessions()
    return {"cleared": count}
