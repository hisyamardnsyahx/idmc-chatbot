# IDMC Chatbot — pipeline v2 + backend RAG + frontend

Local workspace for the IDMC / Portal Data Publik DIY chatbot: a standalone
scraping/chunking pipeline produces a validated JSON handoff bundle, the backend
embeds and indexes it in Chroma and serves chat/retrieval over HTTP, and a Vite
React frontend renders the chat overlay. The pipeline stops before embedding;
only the backend calls Gemini embeddings and writes the vector index.

## Folder map

| Path | Contents |
| --- | --- |
| `backend/` | Python backend. The RAG package lives in `backend/rag/` (`rag.web.app:app`); commands run from `D:\chunking\backend`. |
| `frontend/` | React + Vite chatbot UI (web app). |
| `frontend-extension/` | Browser extension (WXT) that injects the chatbot into the portal. |
| `pipeline/` | Standalone extraction + chunking pipeline, stops at JSON. |
| `data/` | Handoff bundles. `data/handoff/current/` is committed as a sample; backups and archived runs are local-only. |
| `docs/` | Cross-component runbook (`docs/INTEGRATION.md`). |
| `scripts/` | `validate_integration.py`, the offline end-to-end smoke test. |
| `legacy/` | Archived root-era code, data and Chroma: `legacy/root-pipeline-2026-09/`, `legacy/root-data-2026-09/`, `legacy/root-chroma-db-2026-10/`. |

Data backups for rollback: `data/backups/chroma-v1-2026-10-22/` (v1 Chroma
index) and `data/backups/storage-json-v1-2026-10-22/` (v1
`staging_snapshot.json`, `ingest_report.json`, `rag_index_meta.json`). These
folders, the archived `legacy/` tree and live-run handoffs stay on the local
machine and are excluded from git (see `.gitignore`).

## Prerequisites

- Python 3.13 via the `py` launcher (do not use the broken `python` alias).
- Node.js 22 and npm 10.
- A Gemini API key for embeddings and chat (see `backend/rag/.env.example`;
  the real key goes in the root `.env`, which is never committed).
- Valid portal cookies for live crawls. Offline reproduction and tests use
  synthetic fixtures and need no cookies.

## End-to-end order

1. **Crawl** from `D:\chunking\pipeline`:
   ```powershell
   py -B main_orchestrator.py --output-dir runtime/live-v2
   ```
   The bundle is published under `pipeline/runtime/live-v2/` with
   `handoff_manifest.json` written last.
2. **Hand off** by copying the complete bundle (all five files) to
   `D:\chunking\data\handoff\current\`. Never copy while the pipeline is still
   running, and keep the manifest consistent with the payload files.
3. **Ingest** from `D:\chunking\backend`:
   ```powershell
   py -m rag.ingest_from_staging --source ..\data\handoff\current\ready_for_vector_db_v2.json --reindex
   py -m rag.ingest_from_staging --stats
   ```
   `--reindex` clears the active collection first; without it, only changed
   `content_hash` values are re-embedded.
4. **Run the backend** from `D:\chunking\backend`:
   ```powershell
   py -m uvicorn rag.web.app:app --host 127.0.0.1 --port 8001
   ```
5. **Run the frontend** from `D:\chunking\frontend`:
   ```powershell
   npm ci
   npm run dev
   ```
   Vite serves `http://localhost:5173` and proxies `/api` to
   `http://127.0.0.1:8001`.

Offline smoke test from the workspace root:

```powershell
py scripts/validate_integration.py
```

## Index state

- Active collection: `rag_web_gemini-embedding-2_v2` — 507 chunks, 74 catalog
  charts, 20 dashboards, model `gemini-embedding-2`.
- Rollback collection: `rag_web_gemini-embedding-2` — 229 chunks from v1. Set
  `VECTOR_COLLECTION=rag_web_gemini-embedding-2` and restart the backend (or
  inspect with `py -m rag.ingest_from_staging --stats`) to use it. An older
  `rag_web_gemini-embedding-001` (150 chunks) also remains in Chroma.
- Restoring the v1 index from backup: point Chroma at
  `data/backups/chroma-v1-2026-10-22/` and use the v1 storage JSON from
  `data/backups/storage-json-v1-2026-10-22/`.

The live crawl of 2026-10-22 was **partial**: 74 records, 507 chunks, two CCTV
validation failures, valid manifest.

## Repository status

This workspace is a single monorepo (`hisyamardnsyahx/idmc-chatbot`). The
backend, both frontends, pipeline, docs, scripts and the sample handoff bundle
are versioned together. Generated artifacts (`node_modules/`, `dist/`,
`.output/`, `.wxt/`, caches), local vector databases, `data/backups/`,
`data/handoff/live-*/` and `legacy/` are gitignored.

Copy `.env.example` to `.env` and `pipeline/.env.example` to `pipeline/.env`
before running locally. Do not commit `.env`, cookies, API keys or session
tokens.

## Further reading

- [docs/INTEGRATION.md](docs/INTEGRATION.md) — full runbook: pipeline, ingest,
  backend, frontend, configuration, validation and troubleshooting.
- `backend/rag/docs/ARCHITECTURE.md` — backend layering.
- `backend/rag/docs/OPERATIONS.md` — index operations and error handling.
- `pipeline/docs/BACKEND_HANDOFF.md` — handoff contract and manifest rules.
