# Migrasi v2 dan Perapian Struktur Repo

Tanggal: 2026-10-22
Status: menunggu persetujuan

## Tujuan

1. Menjadikan handoff pipeline v2 sebagai jalur produksi utama untuk index,
   retrieval, dan chat.
2. Menghasilkan bundle v2 **baru dari crawl live**, lengkap dengan
   `handoff_manifest.json`, lalu mengindeksnya tanpa menyentuh collection v1.
3. Menyusun workspace menjadi struktur monorepo yang jelas: backend, frontend,
   pipeline, data, dokumentasi, skrip, dan arsip legacy.

## Non-goals

- Tidak mengubah desain UI/Figma.
- Tidak menjalankan tes chat LLM live; kontrak chat tetap diuji dengan stub.
- Tidak menggabungkan sejarah git frontend dan pipeline. Keduanya tetap repo git
  masing-masing di dalam workspace; root tetap bukan git repo.
- Tidak menghapus collection/index v1. v1 dipertahankan untuk rollback.
- Tidak menghapus data sesi pengguna.

## Kondisi awal

- Index aktif: collection `rag_web_gemini-embedding-2`, 229 chunk, 86 chart
  (jalur v1 dari `staging_superset_data.json`).
- Artefak v2 lama di root: 146 chunk, 73 record, 72 slice, status `partial`,
  tanpa manifest, dibuat 29-30 September 2026.
- Pipeline baru mampu menghasilkan bundle v2 dengan manifest; crawl live baru
  sedang berjalan ke `integration/scraping-pipeline/runtime/live-v2`.
- Root workspace mencampur kode pipeline lama, artefak runtime, backend `rag`,
  frontend, dan pipeline baru.

## Keputusan

- Sumber data: **crawl live baru** (dipilih pengguna).
- Struktur: **monorepo penuh + arsip legacy** (interpretasi dari pilihan
  pengguna; path aktif dipindahkan, bukan dipertahankan).
- Migrasi index: collection baru `rag_web_gemini-embedding-2_v2`, dipilih lewat
  `.env`. Collection v1 tidak dihapus.
- Nama paket Python tetap `rag`; import internal tidak diubah.
- Frontend dan pipeline tetap mempertahankan `.git` masing-masing.

## Struktur target

```text
D:\chunking\
  backend\
    rag\                     # paket Python, storage, sessions
  frontend\                  # ex integration/idmc-chatbot
  pipeline\                  # ex integration/scraping-pipeline
  data\
    handoff\
      current\               # bundle yang dipakai backend
      live-2026-10-22\       # hasil crawl live
    backups\
      chroma-v1-2026-10-22\
      storage-json-v1-2026-10-22\
  docs\
  scripts\
  legacy\
    root-pipeline-2026-09\   # kode pipeline lama di root
    root-data-2026-09\       # artefak v1/v2 lama
    root-chroma-db-2026-10\  # chroma_db lama di root
  README.md
  .env
  .env.example
  .gitignore
```

Catatan: `backend/rag/storage` tetap menjadi lokasi Chroma dan sesi aktif agar
perubahan path runtime minimal. `data/` menyimpan handoff dan backup migrasi.

## Perubahan path dan konfigurasi

- `rag/` dipindah ke `backend/rag/`.
- `integration/idmc-chatbot` dipindah ke `frontend/`.
- `integration/scraping-pipeline` dipindah ke `pipeline/`.
- `docs/INTEGRATION.md`, `rag/docs/*`, `frontend` README, dan `pipeline/docs/*`
  diperbarui ke path baru.
- `scripts/validate_integration.py` ditambah `backend` ke `sys.path` dan
  default artefaknya diarahkan ke `data/handoff/current`.
- Root `README.md` ditulis ulang sebagai peta monorepo dan quick start.
- `.env.example` diperbarui untuk `STAGING_SOURCE`, `VECTOR_COLLECTION`, dan
  `RAG_STORAGE`/`CHROMA_PATH` bila diperlukan.
- File legacy root dipindah ke `legacy/`; cache (`__pycache__`,
  `.pytest_cache`, `.dwh_token_cache.json`) dihapus. Duplikat placeholder cookie
  di `.env` dibersihkan tanpa mencetak nilai rahasia.

## Alur migrasi

1. Tunggu crawl live selesai. Validasi exit code, `extraction_report_v2.json`,
   `handoff_manifest.json` (chunk count, SHA-256, byte size), dan status.
2. Salin bundle live ke `data/handoff/live-2026-10-22/`, lalu salin bundle yang
   sama ke `data/handoff/current/`.
3. Backup v1 sebelum menyentuh index:
   - `backend/rag/storage/chroma` -> `data/backups/chroma-v1-2026-10-22/`
   - `staging_snapshot.json`, `ingest_report.json`, `rag_index_meta.json` ->
     `data/backups/storage-json-v1-2026-10-22/`
4. Tambahkan `VECTOR_COLLECTION=rag_web_gemini-embedding-2_v2` ke `.env`.
5. Jalankan ingest nyata dari `backend`:
   `py -m rag.ingest_from_staging --source ..\data\handoff\current\ready_for_vector_db_v2.json --reindex`
6. Verifikasi `/api/stats`, `/api/charts`, dan `/api/search` dengan query nyata.
   Chat LLM live tidak dijalankan.
7. Jalankan ulang seluruh tes backend, pipeline, frontend, dan smoke test
   end-to-end dengan layout baru.
8. Setelah v2 lolos, rapikan legacy dan perbarui dokumentasi.
9. Jangan hapus collection v1 atau backup sampai pengguna menyatakan migrasi
   final.

## Rollback

- Hentikan backend.
- Set `VECTOR_COLLECTION` kembali ke `rag_web_gemini-embedding-2` atau hapus
  baris tersebut.
- Pulihkan `staging_snapshot.json`, `ingest_report.json`, dan
  `rag_index_meta.json` dari backup.
- Collection v1 tetap ada di Chroma; tidak perlu re-embed.
- Bila reorg menimbulkan masalah, kembalikan folder dari path baru ke path lama;
  frontend dan pipeline tetap memiliki riwayat git masing-masing.

## Risiko

- Crawl live bisa partial atau gagal karena cookie/network/browser. Bila gagal,
  jangan diam-diam memakai artefak v2 lama; laporkan dan minta keputusan.
- Embedding Gemini bisa kena kuota/timeout. Karena target collection baru,
  kegagalan tidak merusak v1; ingest dapat diulang.
- Pemindahan folder dapat memutus path dokumentasi/skrip. Semua referensi
  diperbarui dan tes dijalankan dari layout baru.
- Chroma yang dipindah bersama `backend/rag` perlu dicek dengan `/api/stats`
  sebelum ingest v2.
- Root bukan git repo, sehingga pemindahan tidak tercatat sebagai rename git.
  Backup dan daftar move menjadi pengaman.

## Validasi yang harus lulus

- Manifest live cocok dengan chunk list.
- Ingest v2 selesai dan `/api/stats` menunjukkan jumlah chunk yang sama dengan
  manifest.
- `/api/search` mengembalikan sumber dengan `slice_id` dan metadata v2.
- `py -m pytest -q` dari `backend` lulus.
- `py -m unittest discover -s tests` dari `pipeline` lulus.
- `npm run test`, `typecheck`, `lint`, `build` dari `frontend` lulus.
- `py scripts/validate_integration.py` lulus dengan layout baru.
- Tidak ada secret yang tercetak atau masuk artefak yang bisa di-commit.

## Pertanyaan persetujuan

Apakah layout di atas dan interpretasi **monorepo penuh + arsip legacy** sudah
benar? Jika ya, saya lanjut ke rencana eksekusi dan menunggu crawl live selesai
sebelum memindahkan folder aktif.
