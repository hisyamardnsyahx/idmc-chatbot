# Operasional: index, konfigurasi, troubleshooting

## Membangun / memperbarui index

Format yang diprioritaskan adalah handoff v2 dari pipeline standalone. Backend
meng-index chunk v2 apa adanya; chunking hanya dilakukan untuk fallback v1.

Jalankan dari `D:\chunking\backend` (root paket `rag`).

```powershell
cd D:\chunking\backend

# V2: pipeline sudah memotong per baris utuh; backend tidak memotong ulang.
py -m rag.ingest_from_staging --source ..\data\handoff\current\ready_for_vector_db_v2.json --reindex

# V2 staging: memakai ready_for_vector_db_v2.json di direktori yang sama.
py -m rag.ingest_from_staging --source ..\data\handoff\current\staging_idmc_data.json --reindex

# Fallback v1 lama: tetap di-chunk oleh backend.
py -m rag.ingest_from_staging --source staging_superset_data.json --reindex

py -m rag.ingest_from_staging --stats
```

`data/handoff/current` adalah bundle aktif. Arsip run live 2026-10-22 ada di
`data/handoff/live-2026-10-22` (74 records, 507 chunk, status partial).
Path relatif diresolusikan dari direktori kerja; `--source` eksplisit lebih
disarankan daripada hanya mengandalkan `STAGING_SOURCE`.

Alurnya untuk v2: validasi `handoff_manifest.json` (count + SHA-256/byte size)
→ baca chunk tanpa rechunk → sanitasi metadata scalar → tulis
`backend/rag/storage/staging_snapshot.json` dengan `catalog` → embed + upsert Chroma →
tulis `backend/rag/storage/ingest_report.json` dan `backend/rag/storage/rag_index_meta.json`.
`--reindex` mengosongkan koleksi lebih dulu; tanpa itu, hanya chunk dengan
`content_hash` berubah yang di-embed ulang. `--source` juga menerima direktori
dan memilih v2 chunks → v2 staging → v1 secara berurutan. Manifest yang tidak
cocok atau file terpotong ditolak sebelum koleksi disentuh.

Gunakan `py scripts/validate_integration.py` dari root workspace
(`D:\chunking`) untuk smoke test offline (pipeline → Chroma sementara → API)
tanpa memanggil Gemini atau LLM.

## Konfigurasi (`.env`)

| Variabel | Default / contoh | Arti |
|---|---|---|
| `GEMINI_API_KEY` | — | Wajib untuk chat dan embedding |
| `GEMINI_MODEL` | `gemini-3.8-flash` | Model chat utama |
| `GEMINI_FALLBACK_MODELS` | `gemini-3.6-flash,gemini-3.5-flash` | Model cadangan bila utama 503 (dipisah koma, berurutan) |
| `EMBED_MODEL` | `gemini-embedding-2` | Model embedding (aktif) |
| `VECTOR_COLLECTION` | `rag_web_gemini-embedding-2_v2` | Nama koleksi Chroma aktif (507 chunk) |
| `CHROMA_PATH` | `backend/rag/storage/chroma` | Direktori index Chroma (default dari paket) |
| `RAG_STORAGE` | `backend/rag/storage` | Root snapshot, sesi, meta (default dari paket) |
| `RAG_TOP_K` / `RAG_MAX_TOP_K` | `5` / `10` | Default dan batas passages |
| `VECTOR_MIN_SCORE` | `0.68` | Ambang kemiripan cosine untuk menekan hasil yang tidak relevan |
| `RAG_MAX_CHUNK_CHARS` | `1500` | Budget karakter per chunk |
| `EMBED_BATCH` / `EMBED_RPM` / `EMBED_429_RETRIES` | `50` / `90` / `6` | Throttle embedding |
| `RAG_MAX_ROUNDTRIPS` | `5` | Batas ronde function calling |
| `RAG_HISTORY_TURNS` | `10` | Riwayat sesi untuk model |
| `STAGING_SOURCE` | `data/handoff/current/ready_for_vector_db_v2.json` | Path handoff default; relatif terhadap cwd, `--source` lebih disarankan |
| `RAG_CORS_ORIGINS` | `localhost/127.0.0.1:5173,4173` | Origin frontend yang diizinkan (dipisah koma) |

Contoh lengkap ada di `backend/rag/.env.example`. File environment yang
dibaca server adalah `D:\chunking\.env` (root workspace). Tanpa
`VECTOR_COLLECTION` di environment, kode jatuh ke nama
`rag_web_{EMBED_MODEL}` (koleksi v1), jadi pertahankan baris v2 di `.env`.
`CHROMA_PATH`/`RAG_STORAGE` default berada di bawah `backend/rag/storage`.

## Menjalankan server

Dari `D:\chunking\backend`:

```powershell
cd D:\chunking\backend
py -m uvicorn rag.web.app:app --host 127.0.0.1 --port 8001
# shim lama tetap jalan: py -m uvicorn rag.api:app --port 8001
```

## Rollback ke index v1

Koleksi aktif `rag_web_gemini-embedding-2_v2` berisi 507 chunk (74 chart,
20 dashboard). Koleksi v1 `rag_web_gemini-embedding-2` masih ada dengan 229
chunk. Untuk rollback sementara:

```env
VECTOR_COLLECTION=rag_web_gemini-embedding-2
```

Restart server lalu cek `py -m rag.ingest_from_staging --stats`. Backup
fisik v1 ada di `data/backups/chroma-v1-2026-10-22/` dan
`data/backups/storage-json-v1-2026-10-22/` (`staging_snapshot.json`,
`ingest_report.json`, `rag_index_meta.json`). Jangan mencampur model
embedding antar-koleksi.

## Provider chat: Gemini atau endpoint OpenAI-compatible

Default memakai Gemini SDK (`CHAT_PROVIDER` kosong/`gemini`).
Untuk gateway lokal seperti `http://localhost:20128/v1`:

```env
CHAT_PROVIDER=openai-compat
CHAT_BASE_URL=http://localhost:20128/v1
CHAT_MODEL=ocg/muse-spark-1.3-contributor
CHAT_FALLBACK_MODELS=
CHAT_API_KEY=x
CHAT_TIMEOUT_S=120
CHAT_REASONING_EFFORT=minimal
```

Catatan:

- Loop RAG (tools `search_knowledge`/`list_charts`, format respons,
  sitasi) tidak berubah — hanya transport chat yang diganti.
- Backend OpenAI-compatible selalu memakai streaming karena sebagian
  gateway mengembalikan `content` kosong pada panggilan non-streaming.
- Endpoint lokal tersebut tidak mendukung `/v1/embeddings`, jadi
  embedding dan index Chroma tetap memakai Gemini (`EMBED_MODEL`).
  Retrieval (`/api/search`) tidak terpengaruh.
- `CHAT_REASONING_EFFORT=minimal` memangkas waktu berpikir model
  penalaran (mis. `muse-spark`): chat turun dari ~38 dtk ke ~12 dtk
  pada pengujian lokal. Kosongkan untuk perilaku default gateway.
- Setelah mengubah `.env`, restart server (pengaturan dibaca sekali
  saat startup).

## Fallback model chat

Bila model utama mengembalikan 503 (overload), server otomatis mencoba
model cadangan berurutan tanpa mengubah respons API. Kejadian ini dicatat
di log (`Fell back to chat model ...`). 429 (kuota) tidak di-fallback
karena kuota melekat pada project, bukan model.

## Endpoint

- `GET /` — UI chat
- `POST /api/chat` — chat berdasar data dashboard (`{message, session_id?, dashboard_name?, top_k?}`)
- `POST /chat` — alias kompatibilitas untuk proxy frontend lama
- `POST /api/search` — retrieval langsung
- `GET /api/charts` — katalog chart + daftar dashboard
- `GET /api/sessions`, `GET /api/sessions/{id}`, `DELETE /api/sessions/{id}`
- `GET /api/health`, `GET /api/stats`

Respons chat: `{session_id, reply, reply_format, sources}`. `sources` memuat
`slice_id` yang bisa berupa string (mis. `"608"`), bukan hanya integer.

## Integrasi frontend

Frontend ada di `D:\chunking\frontend`. Jalankan backend di port `8001`
dari `D:\chunking\backend`, dan Vite di port `5173`:

```powershell
cd D:\chunking\backend
py -m uvicorn rag.web.app:app --host 127.0.0.1 --port 8001

cd D:\chunking\frontend
npm ci
npm run dev
```

Vite mem-proxy `/api/*` ke `http://127.0.0.1:8001` tanpa rewrite, sehingga
frontend memakai `POST /api/chat`, `GET /api/sessions`, dan seterusnya. CORS
hanya diperlukan bila frontend di-host terpisah dari proxy. Runbook lengkap:
[INTEGRATION.md](../../../docs/INTEGRATION.md).

## Status error API (jujur, bukan 500 buram)

| HTTP | `code` | Arti | Tindakan user |
|---|---|---|---|
| 400 | — | Query/pesan kosong, `top_k` invalid | Perbaiki input |
| 404 | — | Sesi tidak ditemukan | Buat chat baru |
| 429 | `quota_exhausted` | Kuota harian free-tier Gemini habis | Tunggu `retry_after_s` / reset harian |
| 502 | `model_empty`, `tool_loop`, `upstream_unreachable` | Model kosong / berputar / jaringan ke Gemini putus | Coba lagi, sederhanakan pertanyaan |
| 503 | `model_busy` | Gemini overload sementara | Tunggu, retry otomatis 3x |
| 500 | `server_misconfigured`, `chat_failed` | Key/model salah di server, atau error tak terduga | Hubungi admin, sertakan `code` |

## Troubleshooting

| Gejala | Penyebab umum | Tindakan |
|---|---|---|
| `429 quota_exhausted` dari `/api/chat` | Kuota harian free-tier Gemini habis (mis. 20 req/hari untuk flash) | Tunggu hingga `retry_after_s` atau reset harian; pertimbangkan upgrade plan/billing |
| `503 model_busy` dari `/api/chat` | Gemini overload sementara | Tunggu dan retry; backoff 5/10 detik sudah otomatis 3x |
| `GEMINI_API_KEY is missing` | `.env` belum diisi | Salin `backend/rag/.env.example` ke `D:\chunking\.env`, isi key |
| `/api/stats` count 0 | Index belum dibangun | Jalankan ingest dengan `--reindex` |
| `429` saat ingest | Kuota embedding free-tier | Biarkan retry bekerja; jangan naikkan `EMBED_RPM` |
| Lock Chroma (multi-worker) | Satu writer + banyak reader SQLite | Satu proses ingest; API berbagi client; pertimbangkan Qdrant bila persisten |
| Embedding beda model tercampur | Ganti `EMBED_MODEL` tanpa ganti koleksi | Set `VECTOR_COLLECTION` baru setiap ganti model |
