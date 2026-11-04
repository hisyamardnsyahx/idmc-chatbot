# IDMC Chatbot End-to-End Integration Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the `idmc-chatbot` frontend talk to the `rag` FastAPI backend using data produced by the standalone v2 scraping pipeline, with citations, persistent sessions, and validated end-to-end tests.

**Architecture:** The scraping pipeline publishes immutable v2 artifacts (`staging_idmc_data.json`, `ready_for_vector_db_v2.json`, manifest). The backend ingests pre-chunked v2 documents directly into Chroma (no re-chunking), exposes `/api/chat` with sources and sessions, and the frontend renders replies, citations, and real history. The pipeline keeps its boundary: it never embeds or runs RAG.

**Tech Stack:** Python 3.13, FastAPI, ChromaDB, Gemini/OpenAI-compatible chat, React 19 + Vite 8 + TypeScript, Node test runner.

**Spec:** This plan plus the two repository README/HANDOFF documents.

## Global Constraints

- Pipeline stays standalone: no FastAPI, Gemini, Chroma, or RAG imports.
- Frontend must not redesign Figma; reuse existing tokens/components.
- Backend response contract stays `{ session_id, reply, reply_format, sources }`; `{ reply }` remains compatible.
- V2 chunks are whole-row and must never be re-chunked by the backend.
- All metadata sent to Chroma must be scalar (`str | int | float | bool`).
- Default dev ports: backend `8001`, frontend `5173`.
- No secrets in code, logs, tests, or commits.

## Review Focus

- A v2 `slice_id` is a string (e.g. `"608"`); source schemas must not reject it.
- Missing/partial v2 files must fail with an actionable error, never index a truncated snapshot.
- A stale frontend `session_id` must not dead-end the chat; recover by starting a new session.
- History must remain usable when the backend has no sessions or is unreachable.
- Source cards must not leak untrusted HTML; render text only.

---

### Task 1: Backend v2 handoff loader

**Files:**
- Create: `rag/pipeline/handoff.py`
- Modify: `rag/ingest_from_staging.py`
- Test: `rag/tests/test_v2_ingest.py`

**Interfaces:**
- Produces: `load_handoff(source: Path) -> Handoff` where `Handoff` has `documents: list[Document]`, `catalog: list[dict]`, `format: str`, `fingerprint: str`.
- Produces: `detect_source(source: Path | None) -> Path`.

- [ ] Write failing tests for chunk-list input, v2 staging + sibling chunks, v1 regression, and invalid/truncated input.
- [ ] Implement shape detection, scalar metadata sanitization, required-field validation, and catalog extraction.
- [ ] Wire `run_ingest` to use `load_handoff`; write `catalog` into the snapshot and report `format`.
- [ ] Run `py -m pytest rag/tests/test_v2_ingest.py rag/tests/test_ingest.py -q`.

### Task 2: Backend retrieval and API contract

**Files:**
- Modify: `rag/chat/retrieval.py`
- Modify: `rag/core/models.py`
- Modify: `rag/web/schemas.py`
- Modify: `rag/web/app.py`
- Modify: `rag/core/config.py`
- Test: `rag/tests/test_retrieve.py`, `rag/tests/test_api.py`

**Interfaces:**
- `Passage.slice_id: int | str | None`
- `Source.slice_id: int | str | None`
- `retrieval.catalog() -> list[dict]` prefers snapshot `catalog`, falls back to `charts`.
- `POST /chat` alias returns the same body as `POST /api/chat`.
- CORS origins from `RAG_CORS_ORIGINS`.

- [ ] Extend tests for string `slice_id`, v2 catalog, `/chat` alias, and CORS preflight.
- [ ] Implement catalog fallback, schema unions, alias route, and CORS middleware.
- [ ] Run `py -m pytest rag/tests/test_retrieve.py rag/tests/test_api.py -q`.

### Task 3: Pipeline handoff manifest and documentation

**Files:**
- Create: `handoff.py` in `D:\chunking\integration\scraping-pipeline`
- Modify: `main_orchestrator.py`
- Create: `docs/BACKEND_HANDOFF.md`
- Test: `tests/test_pipeline.py`

**Interfaces:**
- Produces `handoff_manifest(payloads: dict, report: dict) -> dict` with `schema_version`, `normalization_version`, `transform_version`, `published_at`, `record_count`, `chunk_count`, and `sha256` of each payload.
- `publish_bundle` receives `handoff_manifest.json` last.

- [ ] Write failing tests for manifest fields and hash stability.
- [ ] Implement manifest and publish it with the bundle.
- [ ] Document the backend ingestion command and artifact contract.
- [ ] Run `py -m unittest discover -s tests -v` and `py -B -m tests.reproduce --output-dir runtime/reproduction`.

### Task 4: Frontend API client and session hook

**Files:**
- Modify: `src/api/chatApi.ts`
- Create: `src/api/sessionsApi.ts`
- Modify: `src/components/chatbot/types.ts`
- Modify: `src/components/chatbot/useChatSession.ts`
- Modify: `vite.config.ts`
- Test: `scripts/ui.test.mjs` (add pure API mapping test if practical)

**Interfaces:**
- `sendChatMessage(message, options: { sessionId?: string; signal?: AbortSignal }) -> Promise<ChatReply>`
- `ChatReply = { sessionId: string; reply: string; replyFormat: string; sources: ChatSource[] }`
- `ChatSource = { dashboard?, chart?, sliceId?: string | number, rowsCovered?, dataAsOf?, possiblyOutdated, relevance, content }`
- `listSessions()`, `getSession(id)` return typed session data.
- `useChatSession` exposes `sessionId`, `loadSession(id)`, `sendMessage`, `resetConversation`.

- [ ] Add source/session types and API client parsing with backend error codes.
- [ ] Add stale-session recovery (404 -> retry once without session id).
- [ ] Point Vite `/api` proxy at `http://127.0.0.1:8001` without stripping `/api`.
- [ ] Run `npm run typecheck` and `npm run lint`.

### Task 5: Frontend citations and real history

**Files:**
- Create: `src/components/chatbot/SourceList.tsx`
- Modify: `src/components/chatbot/MessageBubble.tsx`
- Modify: `src/components/chatbot/MessageList.tsx`
- Modify: `src/components/chatbot/HistoryView.tsx`
- Modify: `src/components/chatbot/ChatOverlay.tsx`
- Modify: `src/App.tsx`
- Modify: `src/components/chatbot/index.ts`
- Test: `scripts/ui.test.mjs`

**Interfaces:**
- `SourceList` renders dashboard, chart, row coverage, data date, stale marker, relevance.
- `MessageList` passes `message.sources` to assistant bubbles.
- `ChatOverlay` fetches history when `historyItems` is not supplied; selecting an item calls `loadSession` and switches to chat.
- `HistoryView` supports `isLoading` and `error` while preserving existing mock behavior.

- [ ] Add static rendering tests for source cards and history loading/error.
- [ ] Implement `SourceList` with existing tokens and safe text rendering.
- [ ] Wire real history list/select; keep mock `historyItems` prop as a test/dev fallback.
- [ ] Run `npm run test`, `npm run typecheck`, `npm run lint`, `npm run build`.

### Task 6: End-to-end validation

**Files:**
- Create: `scripts/validate_integration.py` in `D:\chunking`
- Create: `docs/INTEGRATION.md` in `D:\chunking`

- [ ] Generate pipeline artifacts from the offline reproduction fixture.
- [ ] Ingest the generated v2 chunks into a temporary Chroma collection with deterministic fake embeddings.
- [ ] Start `uvicorn rag.api:app --port 8001`, verify `/api/health`, `/api/stats`, `/chat` alias, and CORS preflight.
- [ ] If the configured chat provider is reachable, run one real `/api/chat`; otherwise run the contract through FastAPI `TestClient` with a stubbed chat service and record the reason.
- [ ] Run all backend tests, all pipeline tests, and all frontend checks.
- [ ] Record exact commands/results in `docs/INTEGRATION.md`.
