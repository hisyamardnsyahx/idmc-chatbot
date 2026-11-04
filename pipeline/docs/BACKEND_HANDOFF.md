# Backend handoff contract

This repository stops at JSON. It does not import FastAPI, Gemini, Chroma,
retrieval or any RAG code. The consumer is the backend package at
`D:\chunking\backend\rag`; run backend commands from `D:\chunking\backend`.
The handoff contract below is unchanged by the current layout.

## Published files

A successful run publishes this bundle into `--output-dir`:

| File | Consumer use |
| --- | --- |
| `staging_idmc_data.json` | Normalized records and provenance; optional backend fallback |
| `ready_for_vector_db_v2.json` | Preferred input: whole-row `{id, page_content, metadata}` chunks |
| `delta_state_v2.json` | Pipeline state; not needed for retrieval |
| `handoff_manifest.json` | Integrity metadata for the three files above |
| `extraction_report_v2.json` | Run status and counts; not part of the manifest |
| `ingestion_errors.log` | Local classified diagnostics; review before sharing |

The manifest is published **last**. `publish_bundle` prepares every payload
before replacing a known-good file, so a consumer that waits for job completion
and checks the manifest cannot silently index a half-written bundle.

The live run writes to `pipeline/runtime/live-v2/`. After the run completes and
the manifest validates, the complete bundle is copied to the workspace as the
active handoff: `D:\chunking\data\handoff\current\`. Only that active copy is
consumed by the backend; `runtime/live-v2/` remains the pipeline's working
output.

## Manifest shape

```json
{
  "schema_version": 2,
  "normalization_version": "2.1.0",
  "transform_version": "2.1.0",
  "published_at": "2026-10-06T04:36:00+00:00",
  "status": "ok",
  "record_count": 2,
  "chunk_count": 37,
  "files": {
    "delta_state_v2.json": {"sha256": "...", "bytes": 1234},
    "ready_for_vector_db_v2.json": {"sha256": "...", "bytes": 5678},
    "staging_idmc_data.json": {"sha256": "...", "bytes": 9012}
  }
}
```

- `sha256` is the hash of the exact published bytes, including the trailing
  newline written by `atomic_write_json`.
- `bytes` is the exact file size.
- `published_at` uses the run clock, so fixed-clock reproduction runs are
  byte-identical.
- `status` is the orchestrator status (`ok` or `partial`).
- The manifest deliberately does not describe itself.

## Consumer rules

1. Read `handoff_manifest.json` first when it exists.
2. Reject the bundle if `chunk_count` does not match the chunk list, or if a
   `sha256`/`bytes` entry does not match the published file.
3. Index `ready_for_vector_db_v2.json` **as-is**. The pipeline owns chunking;
   do not re-chunk or re-split rows.
4. Build the dashboard/chart catalogue from chunk metadata:
   `dashboard_name`, `slice_name` (or `chart_name`), `slice_id` (or `chart_id`).
5. Treat `slice_id` as a string or integer. Superset IDs are usually numeric
   strings; other sources may use non-numeric chart identities.
6. Metadata is Chroma-safe: nulls are omitted; nested lists/objects are
   canonical JSON strings. Do not send the original structured values to Chroma.
7. A zero-row chunk (`row_start = row_end = total_rows = 0`) is metadata-only,
   not extracted table data.
8. Legacy v1 staging (`{"charts": {...}}`) remains a fallback. It is chunked by
   the backend; it is not the preferred v2 path.

## Backend ingestion command

From `D:\chunking\backend` (the parent of the `rag` package):

```powershell
cd D:\chunking\backend
py -m rag.ingest_from_staging `
  --source ..\data\handoff\current\ready_for_vector_db_v2.json `
  --reindex
py -m rag.ingest_from_staging --stats
```

The active collection is `rag_web_gemini-embedding-2_v2` (507 chunks) with
`EMBED_MODEL=gemini-embedding-2`. The v1 collection remains for rollback.
Relative paths resolve from the current directory; prefer an explicit
`--source` over relying on `STAGING_SOURCE`.

Passing `staging_idmc_data.json` (schema v2) also works when the sibling
`ready_for_vector_db_v2.json` exists. Passing a directory auto-detects the v2
chunks first, then v2 staging, then legacy v1.

`--reindex` clears the existing Chroma collection before indexing. Without it,
the ingest is incremental and only changed `content_hash` values are re-embedded.

## Reproduction and validation

```powershell
# from the pipeline root (D:\chunking\pipeline)
py -B -m tests.reproduce --output-dir runtime/reproduction
py -B -m tests.reproduce_frontend --output-dir runtime/frontend-reproduction
py -m unittest discover -s tests -v

# from the workspace root (D:\chunking)
py scripts/validate_integration.py
```

The backend smoke test verifies the manifest, ingests the v2 bundle with
deterministic local embeddings, and exercises retrieval, `/api/chat`, sessions,
the `/chat` alias, CORS and stale-session handling. It does not call a live LLM.
