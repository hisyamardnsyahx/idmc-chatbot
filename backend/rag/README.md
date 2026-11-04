# RAG Chatbot Web DWH Jogja

Chatbot web berdasar data dashboard DWH (kependudukan, kepegawaian,
kesehatan, pertanahan, pangan, UMKM). Jawaban selalu memakai sitasi
sumber: dashboard, chart, rentang baris, dan tanggal data.

Paket Python bernama `rag`; semua perintah di bawah dijalankan dari
`D:\chunking\backend` agar `rag` dapat di-import.

## Struktur

```
backend/rag/
  core/        settings, JSON I/O, logging, domain types
  pipeline/    ingest offline (chunking, embeddings, Chroma)
  chat/        retrieval, prompt, formatter respons, loop Gemini
  sessions/    state percakapan (file JSON per sesi)
  web/         FastAPI app + schemas (lapisan HTTP tipis)
  docs/        ARCHITECTURE, RESPONSE_CONTRACT, OPERATIONS, CONTRIBUTING
  static/      UI chat (Markdown renderer + manajemen sesi)
  templates/   halaman utama
  storage/     snapshot, sesi, meta, dan Chroma (default runtime)
  tests/       suite pytest per lapisan
```

File `api.py`, `config.py`, `chunk.py`, `embed.py`, `store.py`,
`retrieve.py`, `schemas.py`, `session_store.py` di root `backend/rag/`
adalah shim kompatibilitas — entry point lama tetap jalan, kode baru
memakai paket berlapis. Entry point yang disarankan: `rag.web.app:app`.

## Setup

Dari `D:\chunking\backend`:

```powershell
py -m pip install -r rag\requirements.txt
# jika D:\chunking\.env belum ada:
copy rag\.env.example ..\.env
# isi GEMINI_API_KEY di D:\chunking\.env (jangan commit)
```

Root `D:\chunking\.env` adalah file environment backend; contoh lengkap
dan daftar variabel ada di `backend/rag/.env.example`.

## Bangun index

Sumber aktif adalah bundle v2 di `data/handoff/current`:

```powershell
py -m rag.ingest_from_staging --source ..\data\handoff\current\ready_for_vector_db_v2.json --reindex
py -m rag.ingest_from_staging --stats
```

`--reindex` mengosongkan koleksi aktif lebih dulu. Tanpa `--reindex`,
hanya chunk dengan `content_hash` berubah yang di-embed ulang. Path
relatif diresolusikan dari cwd, jadi jalankan dari `backend` atau beri
path absolut.

Koleksi aktif adalah `rag_web_gemini-embedding-2_v2` dengan model
`gemini-embedding-2` (set lewat `.env`); koleksi v1
`rag_web_gemini-embedding-2` (229 chunk) tetap tersedia untuk rollback.

## Jalankan

```powershell
py -m uvicorn rag.web.app:app --port 8001
# buka http://127.0.0.1:8001/
```

## Endpoint

- `GET /` — UI chat (render Markdown + kartu sumber)
- `POST /api/chat` — chat + function calling Gemini
- `POST /chat` — alias kompatibilitas
- `POST /api/search` — retrieval langsung
- `GET /api/charts` — katalog chart
- `GET /api/sessions`, `GET /api/sessions/{id}`, `DELETE /api/sessions/{id}`
- `GET /api/health`, `GET /api/stats`

## Test

```powershell
py -m pytest -q
```

Detail: `docs/ARCHITECTURE.md` (lapisan), `docs/RESPONSE_CONTRACT.md`
(bentuk jawaban), `docs/OPERATIONS.md` (index + troubleshooting),
`docs/CONTRIBUTING.md` (aturan perubahan).
