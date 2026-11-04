# Arsitektur RAG

Paket `backend/rag/` disusun berlapis agar setiap perubahan punya tempat yang jelas.
Aturannya: dependensi mengalir ke bawah, tidak pernah ke atas.

```
backend/rag/web/        HTTP saja (FastAPI, schemas, error mapping)
  │ memakai
backend/rag/chat/       loop Gemini + retrieval + format respons
  │ memakai
backend/rag/sessions/   state percakapan (file JSON per sesi)
  │ dipakai oleh web
backend/rag/pipeline/   ingest offline (chunking, embeddings, Chroma)
  │ memakai
backend/rag/core/       settings, JSON I/O, logging, domain types
```

## `backend/rag/core/` — fondasi bersama

- `config.py` — satu-satunya sumber settings. Dibaca sekali dari
  environment (`.env` didukung). Semua modul membaca atribut
  `settings`, bukan `os.environ` langsung. Nilai tidak valid
  (mis. `RAG_TOP_K=0`) gagal cepat dengan pesan jelas.
- `json_io.py` — `read_json`, `atomic_write_json`, `canonical_json`,
  `md5_hex`. Semua tulis file lewat atomic write (temp + rename)
  agar crash tidak meninggalkan JSON setengah tulis.
- `logging.py` — `setup_logging()` dipakai server dan CLI ingest.
- `errors.py` — vocabulary error bersama (`ChatError` + subclass).
  Provider/SDK exception diterjemahkan di batas modul lewat
  `translate_provider_error()` agar lapisan web selalu memberi status
  jujur (429/502/503), bukan 500 buram.
- `models.py` — `Document` (chunk siap embed), `Passage` (hasil
  retrieval), `ChatTurn` (riwayat untuk model). Objek antar lapis,
  bukan dict lepas.

## `backend/rag/pipeline/` — ingest offline

- `handoff.py` — memuat handoff pipeline v2 (`ready_for_vector_db_v2.json`
  atau `staging_idmc_data.json`), memvalidasi `handoff_manifest.json`
  (count + SHA-256/byte size), menolak chunk duplikat/berpotensi rusak,
  mengubah metadata nested menjadi string JSON scalar, dan membangun
  katalog dashboard/chart. Chunk v2 tidak dipotong ulang.
- `chunking.py` — fallback v1: chart menjadi 1-N `Document` berdasar budget
  karakter (`RAG_MAX_CHUNK_CHARS`, default 1500). Setiap chunk mengulang
  header mandiri (dashboard, chart, kolom, rentang baris) agar terkandung
  utuh saat diambil sendirian. ID deterministik (`slice{ID}-chunk{idx}`)
  agar re-run bersifat upsert.
- `embeddings.py` — wrapper `embed_content` Gemini di balik interface
  `Embedder`. Mode dokumen dan query memakai prefix sesuai kebutuhan
  `gemini-embedding-2`. Batch 50, throttle di bawah `EMBED_RPM`,
  retry 429 hingga `EMBED_429_RETRIES` kali. Test memakai fake
  lewat `set_embedder()`.
- `vector_store.py` — adapter Chroma. `index_documents(docs, fn)`
  hanya me-embed chunk yang `content_hash`-nya berubah, sisanya update
  metadata. `reset_collection()` dipakai `--reindex` agar chunk lama
  tidak tertinggal. `query()` mengembalikan skor cosine, `get_stats()`
  melaporkan count dan meta index.

## `backend/rag/chat/` — retrieval + jawaban

- `retrieval.py` — `search()` memvalidasi query, clamp `top_k`,
  mengembalikan `list[Passage]`. `dashboard_names()` dan `list_charts()`
  membaca `catalog` dari snapshot v2, dengan fallback ke `charts` v1.
- `prompts.py` — kontrak prompt: baris pembuka (dashboard + chart),
  angka sebagai tabel Markdown, blok `Sumber:` dengan rentang baris
  dan tanggal data, catatan parsial/basi, larangan halusinasi.
- `response.py` — `format_reply()` menegakkan kontrak secara defensif:
  merapikan whitespace, membuang blok sumber karangan model,
  membangun ulang blok `Sumber:` dari passages, menambah catatan
  basi/parsial. Jawaban tanpa passages (salam, "tidak ada data")
  tidak diubah.
- `service.py` — loop function calling (tools
  `search_knowledge`, `list_charts`) dalam bentuk pesan polos dan tool
  call JSON. Tidak mengenal SDK apa pun; backend dipilih via settings.
- `providers.py` — backend chat konkret di balik interface `ChatBackend`:
  `GeminiBackend` (SDK google-genai) dan `OpenAICompatBackend`
  (endpoint `/v1/chat/completions` via streaming, mis. gateway lokal).
  `build_backends()` menyusun urutan primary + fallback dari settings.

## `backend/rag/sessions/` — state percakapan

File JSON per sesi di `backend/rag/storage/sessions/`. API internal menerima
`cfg` eksplisit agar test bisa mengisolasi direktori. Riwayat yang
dikirim ke model dibatasi `RAG_HISTORY_TURNS` agar prompt ringkas.

## `backend/rag/web/` — HTTP tipis

- `app.py` — route FastAPI, tanpa logika LLM. `ChatError` dipetakan
  ke status jujur (400 validasi, 404 sesi hilang, 502 model kosong,
  503 model sibuk) lewat exception handler.
- `schemas.py` — model Pydantic request/response. `ChatResponse`
  menyertakan `reply_format: "markdown"` agar frontend tahu cara render.

## File kompatibilitas di root `backend/rag/`

`api.py`, `config.py`, `chunk.py`, `embed.py`, `store.py`,
`retrieve.py`, `schemas.py`, `session_store.py`, `_util.py` adalah
shim tipis ke lokasi baru. Entry point lama (`uvicorn rag.api:app`,
`py -m rag.ingest_from_staging`) tetap jalan, tetapi yang disarankan
adalah `rag.web.app:app`. Kode baru memakai paket berlapis langsung.
Shim berada di dalam `backend/rag/`, bukan di root workspace.

## Index aktif

Koleksi `rag_web_gemini-embedding-2_v2` (model `gemini-embedding-2`)
berisi 507 chunk, 74 chart, dan 20 dashboard. Koleksi v1
`rag_web_gemini-embedding-2` (229 chunk) dipertahankan untuk rollback;
koleksi lama `rag_web_gemini-embedding-001` (150 chunk) juga masih ada.
Snapshot dan Chroma ditulis ke `backend/rag/storage/`; backup v1 ada di
`data/backups/`.
