# Panduan Kontribusi `rag/`

## Tempat menaruh perubahan

- Prompt / bentuk jawaban → `rag/chat/prompts.py` + `rag/chat/response.py`
  (jangan menaruh teks prompt di `rag/web/`).
- Loop model / retry / tools → `rag/chat/service.py`.
- Retrieval / filter → `rag/chat/retrieval.py`.
- Chunking / embedding / Chroma → `rag/pipeline/`.
- State sesi → `rag/sessions/store.py` (teruskan `cfg` eksplisit).
- Route / status HTTP / schemas → `rag/web/`.
- Settings baru → `rag/core/config.py` (satu tempat, validasi di
  `load_settings`), lalu dokumentasikan di `docs/OPERATIONS.md`.

## Aturan

1. **Jangan mengimpor ke atas.** `core` tidak mengimpor paket lain;
   `pipeline` tidak mengimpor `chat`/`web`; `chat` tidak mengimpor `web`.
2. **Inject I/O di batas modul.** Fungsi murni (chunk, format, sesi)
   menerima argumen eksplisit agar mudah diuji tanpa network.
3. **Error bertipe, bukan string.** Tambahkan subclass `ChatError`
   untuk kegagalan baru dan handler HTTP-nya di `rag/web/app.py`.
4. **Setiap perilaku baru punya test.** Letakkan di `rag/tests/`
   dengan nama `test_<area>.py`. Mock di batas I/O (embedder, store,
   `run_chat`) — jangan mem-reimplementasi kode yang diuji.
5. **Kontrak respons dijaga.** Perubahan bentuk jawaban memperbarui
   `docs/RESPONSE_CONTRACT.md` dan `tests/test_response.py` bersamaan.
6. **Shim root tidak diperluas.** File kompatibilitas (`rag/api.py`,
   `rag/retrieve.py`, …) hanya meneruskan; logika baru masuk paket.

## Cek sebelum selesai

```bash
py -m pytest rag/tests -q
py -m py_compile (Get-ChildItem rag -Recurse -Filter *.py | Select-Object -Expand FullName)
```
