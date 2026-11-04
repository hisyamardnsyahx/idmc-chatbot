# Desain: FE lokal sebagai isi extension IDMC Chatbot

- Tanggal: 2026-10-29
- Repo: `hmnnanxiety/idmc-chatbot`
- Basis: `origin/main` (`a34ae8e`)
- Sumber UI: `D:\chunking\frontend` (working tree lokal, HEAD `6116196`)
- Status: menunggu persetujuan

## 1. Tujuan

Menjadikan UI frontend lokal (`D:\chunking\frontend`) sebagai isi extension
Chromium yang sudah ada di repo, lalu menyambungkannya ke backend RAG nyata.

Hasil yang diharapkan:

- Launcher dan panel chatbot muncul di `https://idmc.jogjaprov.go.id/` melalui
  content script dan Shadow DOM yang sudah terbukti di repo.
- Percakapan mengirim `POST /api/chat` dengan `{ message, session_id? }` dan
  menampilkan `reply` Markdown, `session_id`, serta `sources`.
- Pertanyaan lanjutan dalam satu panel memakai `session_id` yang sama.
- Kartu sumber, penanganan error, pemulihan sesi 404, dan perilaku aksesibilitas
  dari FE lokal ikut terbawa.
- Konfigurasi endpoint disiapkan untuk dev lokal dan produksi HTTPS.
- Riwayat chat **tidak ditampilkan** di extension.

## 2. Non-goals

- Tidak mengubah backend RAG.
- Tidak menampilkan History di extension.
- Tidak melakukan streaming, autentikasi, atau dukungan Firefox.
- Tidak men-deploy backend.
- Tidak menambah router, Redux/Zustand, atau library UI baru.
- Tidak mendesain ulang Figma.
- Tidak menyalin riwayat sesi dari server ke UI extension.

## 3. Anti-goals

Extension dianggap gagal jika:

- Menampilkan pertanyaan atau jawaban pengguna lain melalui daftar sesi global.
- Membundel API key model atau rahasia lain di dalam extension.
- Membiarkan content script memanggil URL arbitrer atau mengirim cookie portal.
- Menampilkan jawaban palsu saat backend tidak tersedia.
- Mengubah DOM portal di luar container Shadow DOM milik extension.
- Menghilangkan validasi pengirim, batas panjang pesan, atau pembatalan request
  yang sudah ada di repo.

## 4. Kondisi saat ini

### 4.1 FE lokal

- Vite + React 19 + Tailwind 4.
- Sudah terhubung ke backend: `POST /api/chat`, `GET /api/sessions`,
  `GET /api/sessions/{id}`.
- Menampilkan Markdown, kartu sumber, riwayat sesi, error state, dan pemulihan
  sesi 404.
- Perubahan integrasi masih uncommitted; HEAD tertinggal tiga commit dari
  `origin/main`.

### 4.2 Extension di `origin/main`

- WXT + Manifest V3, content script hanya untuk origin portal, top frame.
- Shadow DOM, styles terisolasi, icon dan font dibundel.
- Background worker memvalidasi pengirim, membuka satu port per request,
  memakai `credentials: 'omit'`, `redirect: 'error'`, dan timeout 25 detik.
- Kontrak masih placeholder: `{ message } -> { reply }`, tanpa `session_id`,
  `sources`, riwayat, atau Markdown terstruktur.
- Riwayat sengaja kosong; tidak ada permissions `storage`, `tabs`, atau
  `scripting`.

### 4.3 Backend

- FastAPI di `127.0.0.1:8001`.
- `POST /api/chat` mengembalikan
  `{ session_id, reply, reply_format, sources }`.
- `GET /api/sessions` mengembalikan semua sesi di server, tanpa autentikasi.
- `CHAT_TIMEOUT_S` default 120 detik, lebih panjang dari batas service worker
  Chromium (sekitar 30 detik).

## 5. Pendekatan yang dipertimbangkan

### 5.1 Cara menggabungkan

| Pendekatan | Keterangan | Keputusan |
| --- | --- | --- |
| A. Scaffold repo + port FE lokal | Branch dari `origin/main`, pertahankan entrypoint, worker, keamanan, dan test extension; ganti UI dan transport dengan versi lokal. | **Dipilih** |
| B. FE lokal + tempel scaffold | Mulai dari Vite app, tambahkan WXT, content script, worker, dan izin dari nol. | Ditolak: keamanan dan test extension harus disusun ulang. |
| C. Bangun ulang bersih | Tulis ulang semuanya dengan kedua repo sebagai referensi. | Ditolak: paling lama dan tidak perlu. |

### 5.2 Riwayat sesi

| Pendekatan | Keterangan | Keputusan |
| --- | --- | --- |
| A. Sembunyikan History | Chat tetap memakai `session_id`, tetapi daftar riwayat tidak pernah dimuat. | **Dipilih** |
| B. Indeks riwayat per-browser | Simpan daftar sesi di `storage.local`. | Ditolak: menambah permission dan kompleksitas. |
| C. Riwayat per-pengguna di backend | Kirim ID instalasi dan filter di backend. | Ditolak: butuh perubahan backend dan bukan autentikasi sungguhan. |

### 5.3 Transport extension

| Pendekatan | Keterangan | Keputusan |
| --- | --- | --- |
| A. Perluas port chat yang ada | Request membawa `sessionId`; response membawa `sessionId`, `reply`, `replyFormat`, `sources`. | **Dipilih** |
| B. Fetch langsung dari content script | Menghindari batas worker, tetapi kena CORS halaman dan memperluas permukaan serangan. | Ditolak |
| C. Port terpisah per endpoint | Lebih banyak kode untuk satu endpoint yang benar-benar dipakai. | Ditolak |

## 6. Keputusan desain

### 6.1 Struktur kerja

- Buat worktree terpisah dari `origin/main` agar working tree lokal dengan
  perubahan yang belum di-commit tidak tersentuh.
- Branch: `feature/local-fe-extension`.
- Entry point extension dipertahankan:
  - `src/entrypoints/chatbot.content.ts`
  - `src/entrypoints/background.ts`
  - `src/extension/*`
  - `wxt.config.ts`
- Komponen, style, API client, dan utilitas dari FE lokal dipindahkan ke branch
  tersebut. `App.tsx` tetap menjadi preview Vite mandiri.
- `ChatOverlay` mendapat prop `historyEnabled?: boolean` dengan default `true`.
  Extension memanggilnya dengan `false`; preview tetap `true`.
- Saat `historyEnabled` false:
  - tombol riwayat tidak dirender;
  - `GET /api/sessions` tidak pernah dipanggil;
  - view History tidak dapat dibuka.
- Kode History tetap dipertahankan untuk preview dan tidak dihapus.

### 6.2 Kontrak data

Tipe dari FE lokal menjadi sumber kebenaran:

```ts
interface ChatSource {
  dashboard?: string
  chart?: string
  sliceId?: string | number
  rowsCovered?: string
  dataAsOf?: string
  possiblyOutdated: boolean
  relevance: number
  content: string
}

interface ChatReply {
  sessionId: string
  reply: string
  replyFormat: string
  sources: ChatSource[]
}
```

Transport UI:

```ts
type ChatTransport = (
  message: string,
  options?: { sessionId?: string; signal?: AbortSignal },
) => Promise<ChatReply>
```

- `useChatSession` menerima transport sebagai parameter (default: preview
  `/api/chat`).
- `sessionId` disimpan di state selama panel terbuka dan dikirim pada setiap
  turn berikutnya.
- Menutup panel mereset percakapan dan `sessionId`; membuka lagi memulai sesi
  baru.
- Jika backend membalas 404 untuk `session_id` lama, UI mencoba sekali lagi
  tanpa `session_id` dan memakai `session_id` baru dari balasan.
- Error 404 yang terjadi lagi, error jaringan, dan response malformed masuk ke
  error state generik.
- Backend unavailable memakai pesan
  `Layanan chatbot belum tersedia. Silakan coba lagi nanti.`

### 6.3 Bridge extension

Protokol port:

```ts
interface ChatPortRequest {
  type: 'chat'
  message: string
  sessionId?: string
}

type ChatPortResponse =
  | {
      ok: true
      sessionId: string
      reply: string
      replyFormat: string
      sources: unknown[]
    }
  | {
      ok: false
      code: 'unavailable' | 'failed' | 'invalid' | 'session_not_found'
    }
```

- `background.ts` tetap mendaftarkan listener secara sinkron.
- Validasi pengirim tetap: extension id, `frameId === 0`, ada `tab.id`, dan
  origin persis `https://idmc.jogjaprov.go.id`.
- Satu port hanya menerima satu request.
- `message` wajib non-kosong dan maksimal 20.000 karakter.
- `sessionId` opsional, berupa string 1–64 karakter `[A-Za-z0-9_-]`.
- Worker memanggil endpoint penuh dari `WXT_CHAT_API_URL` dengan body
  `{ message, session_id? }`.
- Worker memvalidasi response 2xx:
  - `reply` harus string non-kosong;
  - `session_id` opsional menjadi string kosong jika tidak ada;
  - `reply_format` opsional menjadi `markdown`;
  - `sources` harus array; isi tiap item dimapping dan divalidasi di sisi UI.
- Status 404 dipetakan ke `session_not_found`.
- Status non-2xx lain, timeout, network error, atau body malformed dipetakan ke
  `failed`.
- Endpoint kosong dipetakan ke `unavailable` tanpa melakukan fetch.
- `AbortController` tetap dibatalkan saat port disconnect.
- Timeout worker tetap 25 detik; watchdog client 30 detik.
- Tidak ada retry otomatis di worker. Retry 404 hanya dilakukan sekali oleh UI.

### 6.4 Konfigurasi endpoint

- Nama variabel tetap `WXT_CHAT_API_URL`, tetapi nilainya adalah **URL lengkap
  endpoint chat**, bukan base URL.
- Contoh development:
  `WXT_CHAT_API_URL=http://127.0.0.1:8001/api/chat`
- Contoh produksi:
  `WXT_CHAT_API_URL=https://<host>/api/chat`
- Kosong: extension tetap bisa dibuka, tetapi setiap pertanyaan menampilkan
  pesan layanan belum tersedia; tidak ada host permission tambahan.
- Produksi hanya menerima HTTPS. Development/test juga menerima HTTP untuk
  `localhost` dan `127.0.0.1`.
- URL dengan credential atau fragment ditolak.
- Host permission diturunkan dari scheme + hostname endpoint.
- Tidak ada API key di variabel `WXT_`.

### 6.5 UI, style, dan aset

- `overlay.css` tetap mengimpor `index.css` dan font yang dibundel.
- `index.css`, `design-system/tokens.css`, dan `typography.css` dari FE lokal
  menggantikan versi lama.
- Font Plus Jakarta Sans tetap dibundel lewat `@fontsource`, bukan CDN.
- Aset Figma dan ikon dari FE lokal dipindahkan bila belum ada.
- Semua style tetap berada di dalam Shadow DOM; tidak ada selector global baru.
- Markdown memakai `react-markdown` + `remark-gfm`, `skipHtml`, tanpa gambar
  remote, dan link `noopener noreferrer`.
- Blok teks `Sumber:` dari backend dihapus hanya jika `sources` terstruktur ada.
- Kartu sumber tetap non-interaktif seperti di FE lokal.

### 6.6 Riwayat dan privasi

- Extension tidak memanggil `GET /api/sessions`.
- Tidak ada tombol atau view History di extension.
- Tidak ada permission `storage`.
- Preview Vite tetap boleh memakai riwayat server karena hanya untuk
  pengembangan lokal.
- Backend tetap tidak terautentikasi; ini risiko yang diketahui dan di luar
  lingkup perubahan ini.

### 6.7 Test dan verifikasi

Test yang harus lulus:

- `npm run lint`
- `npm run typecheck`
- `npm test`
- `npm run build`
- `npm run test:browser` (setelah `npx playwright install chromium` bila belum)

Cakupan test:

- UI: Markdown, kartu sumber, penghapusan blok `Sumber:`, error state,
  `historyEnabled` menyembunyikan tombol dan tidak memanggil sessions API.
- Protokol: request valid/invalid, `sessionId` diteruskan, response sukses,
  `session_not_found`, `unavailable`, `failed`, timeout, dan pembatalan.
- Worker: validasi pengirim dan endpoint tetap seperti sebelumnya.
- Browser: fixture portal, mock HTTP, pesan pertama + lanjutan memakai
  `session_id`, Markdown, kartu sumber, 404 retry, pembatalan, isolasi style,
  dan penolakan origin/frame lain.

Verifikasi end-to-end lokal:

1. Jalankan backend dari `D:\chunking\backend`:
   `py -m uvicorn rag.web.app:app --host 127.0.0.1 --port 8001`
2. Buat build development dengan
   `WXT_CHAT_API_URL=http://127.0.0.1:8001/api/chat`.
3. Muat `.output/chrome-mv3-dev` di Chromium.
4. Buka portal IDMC, kirim pertanyaan, pastikan balasan Markdown dan kartu
   sumber muncul.
5. Kirim pertanyaan lanjutan dan pastikan `session_id` yang sama dipakai.
6. Hentikan backend, kirim pertanyaan, dan pastikan error state muncul tanpa
   jawaban palsu.

Jika latensi balasan nyata routinely melewati 25 detik, pekerjaan berhenti dan
dilaporkan. Streaming atau API job/polling adalah fitur terpisah, bukan
ditambahkan diam-diam dalam perubahan ini.

### 6.8 Dokumentasi dan hasil akhir

Dokumen yang diperbarui:

- `README.md` — status extension sekarang terhubung ke backend, riwayat
  disembunyikan, cara mengisi `WXT_CHAT_API_URL`.
- `docs/AI_HANDOFF.md` — kontrak baru `session_id` + `sources`.
- `docs/features/extension-api.md` — protokol port baru dan batas timeout.
- `docs/EXTENSION_VALIDATION.md` — cakupan test baru.
- `.env.example` — contoh URL `/api/chat`.

Hasil akhir:

- Branch `feature/local-fe-extension` berisi desain, implementasi, dan test.
- Branch di-push ke `origin`; tidak di-merge ke `main` tanpa persetujuan.
- Working tree lokal `D:\chunking\frontend` dengan perubahan yang belum
  di-commit tidak diubah.

## 7. Risiko dan mitigasi

| Risiko | Mitigasi |
| --- | --- |
| Balasan RAG lebih lama dari 25 detik | Ukur saat verifikasi lokal. Jika sering melewati batas, laporkan dan rencanakan streaming/async terpisah. |
| Sesi backend global | Extension tidak pernah memuat daftar sesi. Risiko API publik tanpa autentikasi dicatat sebagai di luar lingkup. |
| Konflik file antara FE lokal dan `origin/main` | Worktree terisolasi; port per file dengan test sebagai jaring pengaman. |
| Style portal bocor atau style extension rusak | Shadow DOM, scoped tokens, dan browser test isolasi tetap dipertahankan. |
| Perubahan lokal hilang | Tidak ada checkout/reset di working tree lokal; semua pekerjaan dilakukan di worktree baru. |
| Endpoint produksi belum ada | Build produksi menampilkan pesan belum tersedia sampai URL HTTPS diisi. |

## 8. Yang diserahkan ke builder

- Urutan dan pemecahan commit.
- Detail refactor komponen dan penyesuaian test.
- Nama branch worktree dan mekanisme push.
- Pemetaan aset/ikon yang belum ada di branch extension.
- Penyesuaian kecil pada dokumentasi dan `.env.example`.
