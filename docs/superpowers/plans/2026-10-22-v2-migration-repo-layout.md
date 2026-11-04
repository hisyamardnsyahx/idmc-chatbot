# Migrasi v2 + Perapian Struktur Repo Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrasikan index RAG ke handoff v2 hasil crawl live dan susun workspace menjadi monorepo `backend/`, `frontend/`, `pipeline/`, `data/`, `docs/`, `scripts/`, `legacy/`.

**Architecture:** Pipeline tetap standalone dan menghasilkan bundle v2 + manifest. Backend mengonsumsi bundle itu ke collection Chroma baru `rag_web_gemini-embedding-2_v2`; collection v1 tetap utuh untuk rollback. Setelah migrasi terverifikasi, folder aktif dipindah ke layout monorepo dan file pipeline lama diarsipkan.

**Tech Stack:** Python 3.13 (`py`), FastAPI/Chroma/Gemini embeddings, pytest/unittest, React/Vite/TypeScript, PowerShell, git (frontend + pipeline).

**Spec:** `docs/superpowers/specs/2026-10-22-v2-migration-repo-layout-design.md`

## Global Constraints

- Gunakan `py`, bukan `python`.
- Jangan mencetak, menyalin ke log, atau meng-commit nilai `.env`, cookie, API key, atau token.
- Jangan menghapus collection v1 atau backup sampai migrasi dinyatakan final.
- Jangan menjalankan tes chat LLM live; retrieval/chat contract tetap memakai stub.
- Frontend dan pipeline tetap repo git masing-masing; root bukan git repo.
- Tidak ada commit pada plan ini. Perubahan frontend/pipeline tetap di working tree.
- Semua perintah PowerShell dijalankan dari `D:\chunking` kecuali disebutkan lain.
- Jika crawl live abort atau tidak menghasilkan manifest valid, berhenti dan laporkan; jangan diam-diam memakai artefak v2 lama.

## Review Focus

- Bundle live bisa `partial`; pastikan `status`, jumlah record/chunk, dan manifest konsisten sebelum index.
- Ingest embedding bisa gagal di tengah; karena target collection baru, v1 harus tetap dapat dipakai.
- Pemindahan `rag/` dapat mengubah path Chroma/sesi; cek `/api/stats` sebelum dan sesudah ingest.
- Path dokumentasi/skrip mudah tertinggal; grep path lama setelah reorg.
- File `.env` dan cache token mengandung rahasia; pastikan tetap ignored dan tidak masuk output.

---

### Task 1: Validasi hasil crawl live

**Files:**
- Read: `integration/scraping-pipeline/runtime/live-v2/handoff_manifest.json`
- Read: `integration/scraping-pipeline/runtime/live-v2/ready_for_vector_db_v2.json`
- Read: `integration/scraping-pipeline/runtime/live-v2/staging_idmc_data.json`
- Read: `integration/scraping-pipeline/runtime/live-v2/extraction_report_v2.json`

**Interfaces:**
- Produces: keputusan `crawl_status` (`ok`/`partial`/`abort`) dan `expected_chunks` dari manifest.

- [ ] **Step 1: Pastikan proses crawl sudah selesai**

Periksa notifikasi background shell atau jalankan:

```powershell
Get-CimInstance Win32_Process -Filter "Name='py.exe'" | Select-Object ProcessId,CommandLine
```

Expected: tidak ada command line yang menjalankan `main_orchestrator.py`. Jika masih ada, tunggu notifikasi; jangan memindahkan `integration/scraping-pipeline`.

- [ ] **Step 2: Validasi manifest dan isi bundle**

```powershell
py -B -c "import hashlib,json,pathlib; d=pathlib.Path(r'integration/scraping-pipeline/runtime/live-v2'); m=json.loads((d/'handoff_manifest.json').read_text(encoding='utf-8')); docs=json.loads((d/'ready_for_vector_db_v2.json').read_text(encoding='utf-8')); print('status',m.get('status')); print('records',m.get('record_count')); print('chunks',m.get('chunk_count'),len(docs)); [print(name, hashlib.sha256((d/name).read_bytes()).hexdigest()==entry['sha256'], (d/name).stat().st_size==entry['bytes']) for name,entry in m['files'].items()]"
```

Expected: `status` `ok` atau `partial`, `chunks` sama dengan panjang list, dan semua baris file `True True`.

- [ ] **Step 3: Catat hasil crawl**

Baca ringkasan report:

```powershell
Get-Content integration/scraping-pipeline/runtime/live-v2/extraction_report_v2.json -Raw | ConvertFrom-Json | Select-Object status,succeeded,records,chunks,duration_s
```

Expected: `chunks` > 0. Jika `status` `aborted` atau manifest tidak ada, STOP dan laporkan; jangan lanjut ke Task 2.

- [ ] **Step 4: Verifikasi tidak ada kegagalan total**

```powershell
Get-Content integration/scraping-pipeline/runtime/live-v2/extraction_report_v2.json -Raw | ConvertFrom-Json | Select-Object -ExpandProperty failures | Measure-Object
```

Expected: jumlah failure boleh > 0 untuk status `partial`, tetapi `records`/`chunks` harus > 0. Catat failure utama untuk laporan akhir.

---

### Task 2: Pindahkan komponen aktif ke layout monorepo

**Files:**
- Move: `rag/` -> `backend/rag/`
- Move: `integration/idmc-chatbot/` -> `frontend/`
- Move: `integration/scraping-pipeline/` -> `pipeline/`
- Remove: `integration/` jika kosong

**Interfaces:**
- Produces: path baru `backend/rag`, `frontend`, `pipeline`; git frontend/pipeline tetap memiliki `.git`.

- [ ] **Step 1: Pastikan crawl tidak memakai folder pipeline**

Ulangi pemeriksaan proses dari Task 1 Step 1. Jangan lanjut jika masih berjalan.

- [ ] **Step 2: Buat folder tujuan dan pindahkan**

```powershell
New-Item -ItemType Directory -Force backend | Out-Null
Move-Item -LiteralPath 'rag' -Destination 'backend\rag'
Move-Item -LiteralPath 'integration\idmc-chatbot' -Destination 'frontend'
Move-Item -LiteralPath 'integration\scraping-pipeline' -Destination 'pipeline'
if (-not (Get-ChildItem integration -Force -ErrorAction SilentlyContinue)) { Remove-Item integration -Force }
```

Expected: `backend\rag`, `frontend`, `pipeline` ada; `integration` hilang.

- [ ] **Step 3: Verifikasi git frontend/pipeline masih berfungsi**

```powershell
git -C frontend status --short
git -C pipeline status --short
```

Expected: status menampilkan perubahan yang sama seperti sebelum move; tidak ada error `not a git repository`.

- [ ] **Step 4: Verifikasi backend masih membaca index v1**

```powershell
Set-Location backend
py -m rag.ingest_from_staging --stats
Set-Location ..
```

Expected: collection `rag_web_gemini-embedding-2`, count `229`. Jika count berubah atau error, STOP dan pulihkan folder sebelum lanjut.

- [ ] **Step 5: Cek file kunci**

```powershell
Test-Path backend\rag\api.py, frontend\package.json, pipeline\main_orchestrator.py, pipeline\runtime\live-v2\handoff_manifest.json
```

Expected: semua `True`.

---

### Task 3: Perbarui skrip validasi untuk layout baru

**Files:**
- Modify: `scripts/validate_integration.py` (docstring, `sys.path`, `DEFAULT_ARTIFACT`, query smoke test, pesan error)
- Read: `backend/rag/tests/` untuk memastikan import tetap `rag.*`

**Interfaces:**
- Produces: `DEFAULT_ARTIFACT = ROOT / "data" / "handoff" / "current" / "ready_for_vector_db_v2.json"`; `backend` masuk `sys.path`; skrip dijalankan dari root workspace.

- [ ] **Step 1: Ganti sys.path root lama dengan backend**

Di `scripts/validate_integration.py`, ganti blok:

```python
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
```

menjadi:

```python
ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))
```

- [ ] **Step 2: Ubah default artifact**

Ganti `DEFAULT_ARTIFACT` yang menunjuk `integration/scraping-pipeline/runtime/reproduction` menjadi:

```python
DEFAULT_ARTIFACT = (
    ROOT / "data" / "handoff" / "current" / "ready_for_vector_db_v2.json"
)
```

- [ ] **Step 3: Buat smoke test tidak bergantung pada fixture reproduksi**

Saat ini skrip memakai query `"chart small"` dan assertion `slice_id == "608"`, yang hanya cocok untuk fixture offline. Ganti agar memakai data live:

```python
sample_query = " ".join(parsed.documents[0].page_content.split())[:200] or "data"
assert parsed.catalog and all(
    item.get("dashboard_name") and item.get("slice_name") for item in parsed.catalog
)
```

Ganti keempat pemakaian `"chart small"` (search, chat, alias, dan `/api/search`) dengan `sample_query`. Jangan mengubah stub chat atau assertion session.

- [ ] **Step 4: Perbarui docstring dan pesan error**

Ubah docstring:
- "the pipeline's offline reproduction artifact is ingested verbatim" -> "the published live handoff bundle is ingested verbatim".
- "Run from the backend root" -> "Run from the workspace root".

Ubah pesan error menjadi:

```python
"Artifact not found: {artifact}\n"
"Run the live crawl from pipeline/ and copy the published bundle to "
"data/handoff/current/."
```

- [ ] **Step 5: Jalankan tes backend dari layout baru**

```powershell
Set-Location backend
py -m pytest -q
Set-Location ..
```

Expected: seluruh suite lulus (backend saat ini 61 passed; pipeline 184 test terpisah). Jika import `rag` gagal, periksa `BACKEND` path dan `__init__.py`.

- [ ] **Step 6: Pastikan skrip masih bisa diparse tanpa artefak**

```powershell
py -c "import ast,pathlib; ast.parse(pathlib.Path('scripts/validate_integration.py').read_text(encoding='utf-8')); print('syntax-ok')"
```

Expected: `syntax-ok`.

---

### Task 4: Siapkan bundle handoff dan backup v1

**Files:**
- Create: `data/handoff/live-2026-10-22/`
- Create: `data/handoff/current/`
- Create: `data/backups/chroma-v1-2026-10-22/`
- Create: `data/backups/storage-json-v1-2026-10-22/`
- Copy from: `pipeline/runtime/live-v2/`
- Copy from: `backend/rag/storage/`

**Interfaces:**
- Produces: bundle aktif di `data/handoff/current/` dengan manifest sibling; backup v1 untuk rollback.

- [ ] **Step 1: Buat folder data**

```powershell
New-Item -ItemType Directory -Force data\handoff\live-2026-10-22, data\handoff\current, data\backups\storage-json-v1-2026-10-22 | Out-Null
```

- [ ] **Step 2: Salin bundle live dan jadikan current**

```powershell
$files = 'staging_idmc_data.json','ready_for_vector_db_v2.json','delta_state_v2.json','handoff_manifest.json','extraction_report_v2.json'
foreach ($name in $files) {
  Copy-Item -LiteralPath "pipeline\runtime\live-v2\$name" -Destination "data\handoff\live-2026-10-22\$name" -Force
  Copy-Item -LiteralPath "pipeline\runtime\live-v2\$name" -Destination "data\handoff\current\$name" -Force
}
```

Expected: lima file ada di kedua folder.

- [ ] **Step 3: Backup Chroma dan metadata v1**

```powershell
New-Item -ItemType Directory -Force data\backups\chroma-v1-2026-10-22 | Out-Null
Copy-Item -Path 'backend\rag\storage\chroma\*' -Destination 'data\backups\chroma-v1-2026-10-22' -Recurse -Force
Copy-Item -LiteralPath 'backend\rag\storage\staging_snapshot.json','backend\rag\storage\ingest_report.json','backend\rag\storage\rag_index_meta.json' -Destination 'data\backups\storage-json-v1-2026-10-22' -Force
```

Expected: `data\backups\chroma-v1-2026-10-22\chroma.sqlite3` dan tiga JSON backup ada.

- [ ] **Step 4: Validasi manifest lewat loader backend**

```powershell
Set-Location backend
py -c "from pathlib import Path; from rag.pipeline.handoff import load_handoff; h=load_handoff(Path(r'..\data\handoff\current\ready_for_vector_db_v2.json')); print(h.format, len(h.documents), len(h.catalog))"
Set-Location ..
```

Expected: `v2_chunks <expected_chunks> <catalog_count>`; tidak ada error checksum/count.

- [ ] **Step 5: Bandingkan hash current dengan live**

```powershell
$names = 'staging_idmc_data.json','ready_for_vector_db_v2.json','delta_state_v2.json','handoff_manifest.json'
foreach ($n in $names) { $a=(Get-FileHash "data\handoff\live-2026-10-22\$n" -Algorithm SHA256).Hash; $b=(Get-FileHash "data\handoff\current\$n" -Algorithm SHA256).Hash; Write-Output "$n $($a -eq $b)" }
```

Expected: semua `True`.

---

### Task 5: Index v2 ke collection baru

**Files:**
- Modify: `.env` (tambah/ubah `VECTOR_COLLECTION`, tanpa mencetak nilai lain)
- Runtime: `backend/rag/storage/chroma`, `backend/rag/storage/*.json`

**Interfaces:**
- Consumes: `data/handoff/current/ready_for_vector_db_v2.json`
- Produces: collection `rag_web_gemini-embedding-2_v2` dengan jumlah chunk = manifest.

- [ ] **Step 1: Set collection baru di `.env`**

Gunakan PowerShell untuk menghapus baris `VECTOR_COLLECTION` lama lalu menambahkan:

```powershell
$envPath = '.env'
$lines = Get-Content $envPath | Where-Object { $_ -notmatch '^\s*VECTOR_COLLECTION\s*=' }
$lines += 'VECTOR_COLLECTION=rag_web_gemini-embedding-2_v2'
$lines | Set-Content $envPath -Encoding utf8NoBOM
```

Jangan menampilkan isi `.env`.

- [ ] **Step 2: Jalankan ingest nyata**

```powershell
Set-Location backend
py -m rag.ingest_from_staging --source ..\data\handoff\current\ready_for_vector_db_v2.json --reindex
Set-Location ..
```

Expected: proses selesai tanpa error; output menyebut `format v2_chunks`, jumlah chunk, dan collection v2. Ini memanggil Gemini embeddings; jika kuota/timeout, collection v1 tetap aman dan ingest bisa diulang.

- [ ] **Step 3: Verifikasi stats**

```powershell
Set-Location backend
py -m rag.ingest_from_staging --stats
Set-Location ..
```

Expected: `collection` = `rag_web_gemini-embedding-2_v2`; `count` = `expected_chunks` dari Task 1.

- [ ] **Step 4: Verifikasi collection v1 masih ada**

```powershell
Set-Location backend
py -c "import chromadb; from rag.core.config import settings; client=chromadb.PersistentClient(path=str(settings.chroma_dir)); print(sorted(c.name if hasattr(c,'name') else str(c) for c in client.list_collections()))"
Set-Location ..
```

Expected: daftar memuat `rag_web_gemini-embedding-2` dan `rag_web_gemini-embedding-2_v2`.

---

### Task 6: Verifikasi API dan retrieval v2

**Files:**
- Read: `backend/rag/web/app.py`, `backend/rag/chat/retrieval.py`
- Runtime: server port 8001

**Interfaces:**
- Consumes: collection v2 aktif dari `.env`.
- Produces: bukti `/api/stats`, `/api/charts`, `/api/search` memakai v2.

- [ ] **Step 1: Jalankan backend**

```powershell
Start-Process -FilePath 'py' -ArgumentList '-m','uvicorn','rag.api:app','--host','127.0.0.1','--port','8001' -WorkingDirectory (Resolve-Path 'backend') -PassThru
```

Catat PID. Tunggu sampai `/api/health` merespons.

- [ ] **Step 2: Cek stats dan charts**

```powershell
Invoke-RestMethod http://127.0.0.1:8001/api/stats | ConvertTo-Json -Depth 5
Invoke-RestMethod http://127.0.0.1:8001/api/charts | ConvertTo-Json -Depth 5
```

Expected: count = `expected_chunks`; charts/catalog > 0 dan berasal dari dashboard v2.

- [ ] **Step 3: Cek retrieval nyata**

```powershell
$body = @{ query = 'jumlah pegawai'; top_k = 3 } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8001/api/search -ContentType 'application/json' -Body $body | ConvertTo-Json -Depth 6
```

Expected: minimal satu source dengan `slice_id`, `dashboard`, `chart`, dan `content`. Ini memakai embedding Gemini untuk query, bukan LLM chat.

- [ ] **Step 4: Hentikan server**

```powershell
Get-NetTCPConnection -LocalPort 8001 -State Listen -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }
```

Expected: port 8001 tidak lagi listening.

---

### Task 7: Arsipkan legacy dan bersihkan root

**Files:**
- Move: file pipeline lama root -> `legacy/root-pipeline-2026-09/`
- Move: artefak data lama root -> `legacy/root-data-2026-09/`
- Move: `chroma_db/` -> `legacy/root-chroma-db-2026-10/`
- Delete: cache dan file kosong
- Keep: `backend/`, `frontend/`, `pipeline/`, `data/`, `docs/`, `scripts/`, `.env`, `.env.example`, `.gitignore`

**Interfaces:**
- Produces: root hanya berisi komponen aktif, data, dokumentasi, skrip, dan legacy.

- [ ] **Step 1: Buat folder legacy**

```powershell
New-Item -ItemType Directory -Force legacy\root-pipeline-2026-09, legacy\root-data-2026-09, legacy\root-chroma-db-2026-10 | Out-Null
```

- [ ] **Step 2: Pindahkan kode pipeline lama**

```powershell
$legacyCode = 'app.py','chart_service.py','dashboards.py','dwh_client.py','dwh_ingest.py','delta_checker.py','etl_common.py','extractor.py','main_orchestrator.py','transformer.py','vector_store.py','requirements.txt','README.md'
foreach ($name in $legacyCode) { if (Test-Path -LiteralPath $name) { Move-Item -LiteralPath $name -Destination "legacy\root-pipeline-2026-09\$name" -Force } }
```

Expected: file-file itu hilang dari root dan ada di legacy.

- [ ] **Step 3: Pindahkan artefak data lama**

```powershell
$legacyData = 'all_cctv_diy.json','chatbot_metadata.db','delta_state.json','delta_state_v2.json','extraction_report.json','extraction_report_v2.json','ingestion_errors.log','ready_for_vector_db.json','ready_for_vector_db_v2.json','staging_idmc_data.json','staging_superset_data.json','vector_checkpoint_v2.json','dump_data.py'
foreach ($name in $legacyData) { if (Test-Path -LiteralPath $name) { Move-Item -LiteralPath $name -Destination "legacy\root-data-2026-09\$name" -Force } }
```

- [ ] **Step 4: Pindahkan Chroma lama dan hapus cache**

```powershell
if (Test-Path -LiteralPath 'chroma_db') { Move-Item -LiteralPath 'chroma_db' -Destination 'legacy\root-chroma-db-2026-10\chroma_db' -Force }
Remove-Item -LiteralPath '.dwh_token_cache.json' -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath 'pipeline\.dwh_token_cache.json' -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath '__pycache__' -Recurse -Force -ErrorAction SilentlyContinue
Get-ChildItem backend, pipeline, scripts -Directory -Filter '__pycache__' -Recurse -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath '.pytest_cache' -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath 'pipeline\.pytest_cache' -Recurse -Force -ErrorAction SilentlyContinue
```

Expected: root tidak lagi memiliki `chroma_db`, cache, atau token cache. Jangan menghapus `pipeline/.env` atau `.env` root.

- [ ] **Step 5: Bersihkan placeholder dan duplikat key di `.env`**

```powershell
$source = Get-Content '.env'
$filtered = $source | Where-Object { $_ -notmatch 'paste-' }
$seen = @{}
$reversed = for ($i = $filtered.Count - 1; $i -ge 0; $i--) {
  $line = $filtered[$i]
  if ($line -match '^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=') {
    $key = $matches[1]
    if (-not $seen.ContainsKey($key)) { $seen[$key] = $true; $line }
  } else { $line }
}
[array]::Reverse($reversed)
$reversed | Set-Content '.env' -Encoding utf8NoBOM
$check = Get-Content '.env'
Write-Output "placeholders=$(@($check | Where-Object { $_ -match 'paste-' }).Count)"
$dupes = $check | Where-Object { $_ -match '^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=' } | ForEach-Object { ($_ -split '=',2)[0].Trim() } | Group-Object | Where-Object Count -gt 1
Write-Output "duplicate_keys=$(@($dupes).Count)"
```

Expected: `placeholders=0` dan `duplicate_keys=0`. Jangan mencetak isi baris.

- [ ] **Step 6: Verifikasi tidak ada import aktif ke legacy**

```powershell
Get-ChildItem backend\rag, scripts -Recurse -File -Include *.py | Select-String -Pattern 'from (chart_service|dashboards|dwh_client|dwh_ingest|extractor|transformer|vector_store|etl_common|delta_checker) import|import (chart_service|dashboards|dwh_client|dwh_ingest|extractor|transformer|vector_store|etl_common|delta_checker)'
```

Expected: tidak ada hasil. Pipeline sengaja dikecualikan karena memiliki modul standalone sendiri.

- [ ] **Step 7: Cek root**

```powershell
Get-ChildItem -Force | Select-Object Mode,Name
```

Expected: hanya `backend`, `frontend`, `pipeline`, `data`, `docs`, `scripts`, `legacy`, `README.md`, `.env`, `.env.example`, `.gitignore`.

---

### Task 8: Perbarui dokumentasi dan contoh environment

**Files:**
- Rewrite: `README.md`
- Modify: `docs/INTEGRATION.md`
- Modify: `backend/rag/README.md`
- Modify: `backend/rag/docs/OPERATIONS.md`
- Modify: `backend/rag/docs/ARCHITECTURE.md`
- Modify: `backend/rag/.env.example`
- Modify: `pipeline/docs/BACKEND_HANDOFF.md`
- Modify: `frontend/README.md`
- Modify: `.env.example`

**Interfaces:**
- Produces: semua perintah dokumentasi memakai layout baru dan collection v2.

- [ ] **Step 1: Tulis README root baru**

Isi minimal: peta folder, prasyarat, urutan crawl -> handoff -> ingest -> backend -> frontend, dan tautan ke `docs/INTEGRATION.md`. Sebut collection v2, lokasi backup v1, dan bahwa root bukan git repo.

- [ ] **Step 2: Perbarui dokumentasi backend**

Di `backend/rag/README.md`, `docs/OPERATIONS.md`, dan `docs/ARCHITECTURE.md`:
- Ganti perintah dari root `rag/` menjadi `cd backend` lalu `py -m ...`.
- Ganti contoh sumber menjadi `..\data\handoff\current\ready_for_vector_db_v2.json`.
- Pastikan perintah tes menjadi `py -m pytest -q` dari `backend/`.
- Sebut collection default v2 hanya jika `.env` sudah diset; jika tidak, jelaskan rollback ke v1.

- [ ] **Step 3: Perbarui dokumentasi pipeline dan frontend**

Di `pipeline/docs/BACKEND_HANDOFF.md`:
- Ganti path lama `integration/scraping-pipeline` -> `pipeline`.
- Jelaskan bundle live ada di `pipeline/runtime/live-v2/` dan disalin ke `data/handoff/current/`.
- Jangan mengubah kontrak manifest.

Di `frontend/README.md`:
- Hapus pernyataan "No backend/RAG/API integration yet" dan "No persistent chat history/auth" karena sudah tidak benar.
- Dokumentasikan `npm ci`, `npm run dev`, proxy `/api` ke `http://127.0.0.1:8001`, serta `npm run test`, `typecheck`, `lint`, `build`.
- Ganti path project root lama dengan `D:\chunking\frontend`.

- [ ] **Step 4: Perbarui kedua contoh environment**

Root `.env.example` (cookie pipeline + backend):
```dotenv
# Backend RAG (detail: backend/rag/.env.example)
EMBED_MODEL=gemini-embedding-2
VECTOR_COLLECTION=rag_web_gemini-embedding-2_v2
# STAGING_SOURCE=data/handoff/current/ready_for_vector_db_v2.json
```

`backend/rag/.env.example`:
- Ganti `VECTOR_COLLECTION` menjadi `rag_web_gemini-embedding-2_v2`.
- Komentari `RAG_STORAGE` dan `CHROMA_PATH`; biarkan default `backend/rag/storage` yang dihitung dari lokasi paket.
- Ganti contoh `STAGING_SOURCE` menjadi `data/handoff/current/ready_for_vector_db_v2.json` dan jelaskan bahwa path relatif diresolusi dari cwd; CLI dianjurkan memakai `--source`.
- Jangan menaruh nilai secret.

- [ ] **Step 5: Cek path lama**

```powershell
Get-ChildItem README.md, docs, backend\rag\docs, pipeline\docs, frontend\README.md -Recurse -File -Include *.md | Select-String -Pattern 'integration[/\\]scraping-pipeline|integration[/\\]idmc-chatbot|D:\\chunking\\rag'
```

Expected: tidak ada hasil, kecuali dokumen historis di `docs/superpowers/plans/` dan `docs/superpowers/specs/`.

---

### Task 9: Validasi penuh layout baru

**Files:**
- Test: backend suite, pipeline suite, frontend suite, smoke test
- Read: `scripts/validate_integration.py`

**Interfaces:**
- Consumes: `data/handoff/current`, collection v2, layout baru.
- Produces: laporan bukti akhir.

- [ ] **Step 1: Backend**

```powershell
Set-Location backend
py -m pytest -q
Set-Location ..
```

Expected: backend suite lulus (61 passed saat plan diperbarui; angka bisa berubah bila tes ditambah).

- [ ] **Step 2: Pipeline**

```powershell
Set-Location pipeline
py -m unittest discover -s tests
Set-Location ..
```

Expected: `OK`, 184+ tests.

- [ ] **Step 3: Frontend**

```powershell
Set-Location frontend
npm run test
npm run typecheck
npm run lint
npm run build
Set-Location ..
```

Expected: semua lulus.

- [ ] **Step 4: Smoke test end-to-end**

```powershell
py scripts/validate_integration.py
```

Expected: format `v2_chunks`, jumlah chunk sesuai `data/handoff/current`, charts/catalog > 0, sources > 0, session turns > 0, dan semua check lulus. Tes ini memakai embedding fake + stub chat, bukan LLM live.

- [ ] **Step 5: Audit secret dan whitespace**

```powershell
git -C frontend diff --check
git -C pipeline diff --check
git -C frontend status --short
git -C pipeline status --short
```

Expected: tidak ada whitespace error; `.env`, token cache, `node_modules`, `dist`, dan runtime tidak muncul sebagai file yang akan di-commit. Jangan mencetak isi `.env`.

---

### Task 10: Laporan akhir dan rollback

**Files:**
- Create/update: `docs/INTEGRATION.md` bagian hasil migrasi
- Read: `data/backups/`, `backend/rag/storage/rag_index_meta.json`

**Interfaces:**
- Produces: ringkasan koleksi v1/v2, jumlah chunk, lokasi backup, dan perintah rollback.

- [ ] **Step 1: Catat statistik akhir**

```powershell
Set-Location backend
py -m rag.ingest_from_staging --stats
Set-Location ..
```

Expected: collection v2 dan count final.

- [ ] **Step 2: Verifikasi backup**

```powershell
Test-Path data\backups\chroma-v1-2026-10-22\chroma.sqlite3
Test-Path data\backups\storage-json-v1-2026-10-22\staging_snapshot.json
```

Expected: keduanya `True`.

- [ ] **Step 3: Tulis perintah rollback di dokumentasi**

Dokumentasikan: set `VECTOR_COLLECTION=rag_web_gemini-embedding-2`, pulihkan tiga JSON dari backup, restart backend. Jangan menyalin isi secret.

- [ ] **Step 4: Laporkan**

Sertakan: status crawl, jumlah record/chunk, collection v2, hasil tes, path baru, dan catatan bahwa v1 tetap tersedia untuk rollback. Sebutkan bahwa tes chat LLM live tidak dijalankan.
