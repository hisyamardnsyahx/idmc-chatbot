# Integrasi IDMC Chatbot: pipeline v2 → backend RAG → frontend

Dokumen ini adalah runbook lokal untuk tiga komponen:

| Komponen | Lokasi | Peran |
| --- | --- | --- |
| Scraping pipeline v2 | `D:\chunking\pipeline` | Ekstraksi + normalisasi + chunking; berhenti sebelum embedding |
| Backend RAG | `D:\chunking\backend\rag` | Ingest ke Chroma, retrieval, chat, sesi, HTTP API |
| Frontend | `D:\chunking\frontend` | Chat overlay, sitasi, riwayat sesi |

Batas kontrak tetap dijaga: pipeline tidak mengimpor FastAPI, Gemini, Chroma,
atau kode RAG. Backend adalah satu-satunya pihak yang membuat embedding dan
meng-indeks.

## Alur data

```text
portal / fixture
  → pipeline: staging_idmc_data.json
  → pipeline: ready_for_vector_db_v2.json   (whole-row chunks)
  → pipeline: handoff_manifest.json         (counts + SHA-256, published last)
  → salin bundle ke data/handoff/current
  → backend: validasi manifest
  → backend: chunk v2 di-index apa adanya (tanpa rechunk)
  → Chroma + backend/rag/storage/staging_snapshot.json (catalog)
  → POST /api/chat → {session_id, reply, reply_format, sources}
  → frontend: bubble + kartu sumber + riwayat sesi
```

## Prasyarat

- Python 3.13 (`py`), bukan alias `python` yang rusak di mesin ini.
- Node.js 22 + npm 10.
- Dependensi backend sudah terpasang (`fastapi`, `chromadb`, `pytest`, dll).
- Dependensi frontend: `npm ci` di `D:\chunking\frontend`.
- Untuk crawl live pipeline: cookie portal di `.env` pipeline dan akses
  jaringan. Untuk validasi offline, fixture sintetis tidak memerlukan cookie.

## 1. Menyiapkan artefak pipeline

Reproduksi offline (disarankan untuk validasi):

```powershell
cd D:\chunking\pipeline
py -B -m tests.reproduce --output-dir runtime/reproduction
py -B -m tests.reproduce_frontend --output-dir runtime/frontend-reproduction
```

Hasil yang dipakai backend:

```text
runtime/reproduction/ready_for_vector_db_v2.json
runtime/reproduction/handoff_manifest.json
runtime/reproduction/staging_idmc_data.json
```

Crawl live (hanya bila cookie/akses portal siap):

```powershell
cd D:\chunking\pipeline
py -B main_orchestrator.py --output-dir runtime/live-v2
```

Pipeline menulis manifest terakhir. Jangan mengonsumsi file saat job masih
berjalan. Setelah run selesai dan manifest valid, salin seluruh bundle ke
`D:\chunking\data\handoff\current\` — direktori itulah yang dibaca backend
sebagai sumber aktif:

```powershell
Copy-Item D:\chunking\pipeline\runtime\live-v2\* D:\chunking\data\handoff\current\
```

Bundle live yang diarsipkan ada di `data/handoff/live-2026-10-22/`.
Kontrak lengkap: `pipeline/docs/BACKEND_HANDOFF.md`.

## 2. Ingest ke backend

Dari `D:\chunking\backend`:

```powershell
cd D:\chunking\backend
py -m rag.ingest_from_staging `
  --source ..\data\handoff\current\ready_for_vector_db_v2.json `
  --reindex
```

Alternatif:

```powershell
# staging v2; backend memakai ready_for_vector_db_v2.json sibling
py -m rag.ingest_from_staging --source ..\data\handoff\current\staging_idmc_data.json --reindex

# legacy v1; backend melakukan chunking v1
py -m rag.ingest_from_staging --source staging_superset_data.json --reindex

# cek index
py -m rag.ingest_from_staging --stats
```

Perilaku penting:

- `--reindex` mengosongkan koleksi lebih dulu; tanpa itu ingest bersifat incremental.
- Chunk v2 tidak dipotong ulang.
- Manifest divalidasi: `chunk_count`, `sha256`, dan `bytes` harus cocok.
- Metadata nested diserialisasi menjadi string JSON agar aman untuk Chroma.
- `slice_id` boleh string (mis. `"608"`) atau integer.
- Snapshot menyimpan `catalog` untuk `/api/charts` dan filter dashboard.
- Path relatif di `STAGING_SOURCE`/`--source` diresolusikan dari direktori
  kerja; lebih aman selalu memberi `--source` eksplisit dari `backend`.

## 3. Menjalankan backend

```powershell
cd D:\chunking\backend
py -m uvicorn rag.web.app:app --host 127.0.0.1 --port 8001
```

Cek cepat:

```powershell
Invoke-RestMethod http://127.0.0.1:8001/api/health
Invoke-RestMethod http://127.0.0.1:8001/api/stats
Invoke-RestMethod http://127.0.0.1:8001/api/charts
```

Endpoint:

| Method | Path | Keterangan |
| --- | --- | --- |
| POST | `/api/chat` | Chat + `session_id` + `sources` |
| POST | `/chat` | Alias kompatibilitas |
| POST | `/api/search` | Retrieval langsung |
| GET | `/api/charts` | Katalog chart + dashboard |
| GET | `/api/sessions` | Daftar sesi |
| GET | `/api/sessions/{id}` | Detail sesi + turns + sources |
| DELETE | `/api/sessions/{id}` | Hapus sesi |
| GET | `/api/health`, `/api/stats` | Health dan statistik index |

## 4. Menjalankan frontend

```powershell
cd D:\chunking\frontend
npm ci
npm run dev
```

Buka `http://localhost:5173`. Vite mem-proxy `/api/*` ke
`http://127.0.0.1:8001` **tanpa** rewrite, jadi path backend dan frontend sama.

Perilaku frontend:

- Pesan user dikirim ke `POST /api/chat`; `session_id` disimpan untuk turn berikutnya.
- Balasan asisten dirender sebagai Markdown (GFM).
- Blok teks `Sumber:` dari backend diganti kartu sumber terstruktur; catatan
  basi/parsial di belakangnya tetap dipertahankan.
- Tombol riwayat memuat `GET /api/sessions`; memilih item memuat detail sesi
  dan memulihkan percakapan.
- Sesi 404 (mis. dihapus server) dipulihkan dengan membuat sesi baru dan
  mengirim ulang pesan sekali.
- Error backend dengan `code`/`retry_after_s` ditampilkan sebagai pesan error,
  bukan crash.

## 5. Konfigurasi backend

Variabel penting di `D:\chunking\.env` (root workspace adalah file environment
backend; contoh lengkap: `backend/rag/.env.example`):

| Variabel | Contoh / default | Arti |
| --- | --- | --- |
| `GEMINI_API_KEY` | `<secret>` | Embedding dan chat; jangan commit |
| `EMBED_MODEL` | `gemini-embedding-2` | Harus konsisten dengan koleksi |
| `VECTOR_COLLECTION` | `rag_web_gemini-embedding-2_v2` | Nama koleksi Chroma aktif |
| `CHROMA_PATH` | `backend/rag/storage/chroma` | Direktori index Chroma (default) |
| `RAG_STORAGE` | `backend/rag/storage` | Root snapshot, sesi, meta (default) |
| `STAGING_SOURCE` | `data/handoff/current/ready_for_vector_db_v2.json` | Default sumber ingest; path relatif dari cwd, `--source` lebih disarankan |
| `RAG_CORS_ORIGINS` | `http://localhost:5173,...` | Hanya bila frontend di-host terpisah |
| `CHAT_PROVIDER` | `gemini` / `openai-compat` | Provider chat |
| `GEMINI_MODEL` | `gemini-3.8-flash` | Model chat Gemini |
| `CHAT_BASE_URL` | `http://localhost:20128/v1` | Gateway OpenAI-compatible |

`RAG_CORS_ORIGINS` default mencakup `localhost`/`127.0.0.1` port 5173 dan 4173.
Setelah mengubah `.env`, restart server.

### Rollback ke index v1

Koleksi v2 aktif berisi 507 chunk. Koleksi v1
`rag_web_gemini-embedding-2` masih tersimpan dengan 229 chunk (koleksi lama
`rag_web_gemini-embedding-001` juga masih ada dengan 150 chunk). Untuk rollback:

```env
VECTOR_COLLECTION=rag_web_gemini-embedding-2
```

Restart backend (atau cek `py -m rag.ingest_from_staging --stats`). Backup v1:
Chroma di `data/backups/chroma-v1-2026-10-22/`, JSON storage v1 di
`data/backups/storage-json-v1-2026-10-22/`.

## 6. Validasi yang sudah dijalankan

Hasil di bawah adalah run terakhir yang tercatat. Task 9 akan menjalankan ulang
seluruh suite; jangan menganggap angka ini sebagai hasil terkini.

### Backend

```powershell
cd D:\chunking\backend
py -m pytest -q
# 61 passed
```

### Pipeline

```powershell
cd D:\chunking\pipeline
py -m unittest discover -s tests -v
# 184 tests expected; suite dijalankan ulang di Task 9
```

Reproduksi deterministik (fixture sintetis kecil; ukuran bukan index aktif):

```text
runtime/reproduction dan runtime/frontend-reproduction dipublikasikan dua kali.
identical_runs: true (staging, chunks, delta, manifest)
```

### Frontend

```powershell
cd D:\chunking\frontend
npm run test        # 17 passed (run terakhir)
npm run typecheck
npm run lint
npm run build
```

### End-to-end offline

```powershell
cd D:\chunking
py scripts/validate_integration.py
```

Hasil aktual 2026-10-22 terhadap bundle v2 aktif:

```json
{
  "format": "v2_chunks",
  "chunks": 507,
  "charts": 74,
  "dashboards": 20,
  "passages": 3,
  "sources": 3,
  "session_turns": 2,
  "checks": [
    "manifest", "ingest", "chroma", "catalog", "search",
    "api.chat", "api.sessions", "api.chat alias",
    "stale session 404", "cors", "api.search"
  ]
}
```

Semua 11 check lulus. Smoke test memakai embedding deterministik dan stub chat.
Ini menguji parser handoff, manifest, Chroma, retrieval, FastAPI, CORS, sesi,
dan bentuk respons; **bukan** kualitas jawaban LLM.

Catatan crawl live 2026-10-22: status **partial** — 74 records, 507 chunk,
dua kegagalan validasi CCTV, manifest valid. Kegagalan tercatat di
`extraction_report_v2.json`; periksa sebelum memakai bundle.

### Tes LLM live

Tes LLM live **sengaja dilewati** pada validasi ini. Kontrak API tetap diuji
dengan stub deterministik. Untuk mencoba Gemini nanti, ubah `.env` (jangan
commit):

```env
CHAT_PROVIDER=gemini
GEMINI_MODEL=gemini-3.8-flash
GEMINI_API_KEY=<secret>
```

Lalu restart backend dan kirim satu pertanyaan. Index embedding yang sudah ada
tetap dapat dipakai selama `EMBED_MODEL`/`VECTOR_COLLECTION` tidak berubah.

## Troubleshooting

| Gejala | Penyebab | Tindakan |
| --- | --- | --- |
| `ECONNREFUSED` di frontend | Backend belum jalan di 8001 | Jalankan uvicorn dari `backend`, cek `/api/health` |
| `/api/chat` 404 | `session_id` lama sudah dihapus | Frontend otomatis retry tanpa sesi; pastikan backend hidup |
| CORS error | Frontend di-host di origin lain | Tambah origin ke `RAG_CORS_ORIGINS`, restart |
| `/api/stats` count 0 | Index belum dibangun / koleksi salah | Jalankan ingest `--reindex` dari `backend` |
| Manifest mismatch | File terpotong / bundle tidak lengkap | Salin ulang bundle lengkap; jangan index paksa |
| `--source` tidak ditemukan | Path relatif dihitung dari cwd | Gunakan path absolut atau jalankan dari `D:\chunking\backend` |
| `slice_id` hilang di sumber | Metadata pipeline lama | Regenerasi chunk v2 atau cek `chart_id` |
| Chat timeout | Provider lambat/tidak siap | Naikkan `CHAT_TIMEOUT_S` atau gunakan stub/tes offline |

## Keamanan dan batasan

- Jangan commit `.env`, cookie, API key, atau token gateway.
- Jangan mencampur koleksi Chroma dengan model embedding berbeda.
- `DELETE /api/sessions/{id}` tersedia di backend, tetapi UI sengaja belum
  menambah tombol hapus agar tidak mengubah desain Figma.
- Pipeline live membutuhkan cookie portal yang valid; validasi repo ini memakai
  fixture sintetis, bukan snapshot produksi.
- Tes live LLM belum dijalankan; jangan mengklaim kualitas jawaban model dari
  smoke test offline.
- Root workspace adalah monorepo git. Semua komponen (`backend/`, `frontend/`,
  `frontend-extension/`, `pipeline/`) di-commit dari root; jangan membuat repo
  git terpisah di dalam subfolder.
