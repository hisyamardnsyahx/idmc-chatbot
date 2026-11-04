# Integrasi FE Lokal ke Extension — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Menjadikan FE lokal (`D:\chunking\frontend`) isi extension Chromium di `origin/main`, terhubung ke `POST /api/chat` dengan `session_id` dan `sources`, tanpa menampilkan riwayat sesi.

**Architecture:** Branch baru dari `origin/main` mempertahankan content script, Shadow DOM, background worker, validasi pengirim, dan test extension. Lapisan UI/API dari FE lokal dipindahkan ke atas scaffold itu. Transport extension diperluas dari `{message} -> {reply}` menjadi `{message, sessionId?} -> {sessionId, reply, replyFormat, sources}`. Riwayat sesi disembunyikan di extension; preview Vite tetap memakai riwayat server.

**Tech Stack:** WXT 0.21.5, Manifest V3, React 19, TypeScript 6, Tailwind CSS 4, Vite 8, Playwright 1.62.1, Node 22+.

**Spec:** `docs/superpowers/specs/2026-10-29-extension-local-fe-design.md`

## Global Constraints

- Node.js 22+; Chrome/Edge 120+; jangan menambah runtime dependency baru.
- Extension hanya cocok untuk `https://idmc.jogjaprov.go.id/*`, top frame, `document_idle`.
- Semua UI berada di Shadow DOM; jangan menambah selector global atau mengubah DOM portal di luar container extension.
- `WXT_CHAT_API_URL` adalah URL lengkap endpoint chat (contoh `https://host/api/chat`), bukan base URL.
- Produksi hanya HTTPS. Development/test boleh HTTP untuk `localhost`/`127.0.0.1`.
- Worker timeout 25 detik; client watchdog 30 detik; pesan maksimal 20.000 karakter; session id 1–64 karakter `[A-Za-z0-9_-]`.
- Fetch worker memakai `credentials: 'omit'` dan `redirect: 'error'`.
- Tidak ada API key atau rahasia di variabel `WXT_`.
- Extension tidak boleh memanggil `GET /api/sessions`; tombol History tidak dirender.
- Working tree `D:\chunking\frontend` tidak boleh di-checkout, di-reset, atau diubah. Semua pekerjaan di worktree terpisah.
- Jangan mengubah backend RAG.
- Jangan merge ke `main`; cukup push branch.

## Review Focus

- **404 di tengah percakapan:** sesi backend hilang saat user mengirim turn lanjutan. Harapan: retry sekali tanpa `session_id`, tampilkan jawaban baru, jangan menduplikasi bubble user.
- **Backend belum dikonfigurasi:** `WXT_CHAT_API_URL` kosong. Harapan: pesan `Layanan chatbot belum tersedia. Silakan coba lagi nanti.`, tanpa request jaringan dan tanpa jawaban palsu.
- **`sources` hilang/malformed:** backend mengembalikan `sources: null`, item non-object, atau field snake_case tidak lengkap. Harapan: balasan Markdown tetap tampil, kartu sumber hanya berisi item valid, tidak ada crash.
- **Isolasi portal:** style global portal, tombol, input, dan keyboard shortcut tidak boleh berubah; tombol History tidak muncul dan tidak ada request `/api/sessions`.
- **Balasan lama/timeout:** RAG melewati 25 detik. Harapan: loading berhenti dan error state muncul; tidak menggantung atau menampilkan jawaban terlambat setelah panel ditutup.

---

### Task 0: Siapkan worktree terisolasi dan commit desain

**Files:**
- Create: `docs/superpowers/specs/2026-10-29-extension-local-fe-design.md`
- Create: `docs/superpowers/plans/2026-10-29-extension-local-fe-integration.md`

**Interfaces:**
- Consumes: `origin/main` at `a34ae8e`; local design/plan files in `D:\chunking\frontend`.
- Produces: worktree `D:\chunking\frontend-extension` on branch `feature/local-fe-extension`.

- [ ] **Step 1: Create the worktree from `origin/main`**

From `D:\chunking\frontend`:

```powershell
git worktree add D:\chunking\frontend-extension -b feature/local-fe-extension origin/main
```

Expected: `Preparing worktree ... HEAD is now at a34ae8e`.

- [ ] **Step 2: Install dependencies in the worktree**

```powershell
cd D:\chunking\frontend-extension
npm ci
```

Expected: install completes and `wxt prepare` runs from `postinstall`.

- [ ] **Step 3: Copy the design and plan into the worktree**

```powershell
$local = 'D:\chunking\frontend'
New-Item -ItemType Directory -Force docs\superpowers\specs, docs\superpowers\plans | Out-Null
Copy-Item "$local\docs\superpowers\specs\2026-10-29-extension-local-fe-design.md" 'docs\superpowers\specs\' -Force
Copy-Item "$local\docs\superpowers\plans\2026-10-29-extension-local-fe-integration.md" 'docs\superpowers\plans\' -Force
```

- [ ] **Step 4: Commit the documents and verify a clean baseline**

```powershell
git add docs/superpowers
git commit -m "docs: add local FE extension design and plan"
git status --short
git log --oneline -3
```

Expected: `git status --short` is empty; the log shows the docs commit on top of `a34ae8e`.

---

### Task 1: Pindahkan UI/API FE lokal dan overlay sadar-sesi

**Files:**
- Create: `src/api/chatTransport.ts`
- Create: `src/api/types.ts`
- Create: `src/api/mapSource.ts`
- Create: `src/api/client.ts`
- Create: `src/api/sessionsApi.ts`
- Create: `src/lib/formatReply.ts`
- Create: `src/components/chatbot/SourceList.tsx`
- Modify: `src/api/chatApi.ts`
- Modify: `src/api/chatRequest.ts`
- Modify: `src/components/chatbot/types.ts`
- Modify: `src/components/chatbot/MessageBubble.tsx`
- Modify: `src/components/chatbot/MessageList.tsx`
- Modify: `src/components/chatbot/HistoryView.tsx`
- Modify: `src/components/chatbot/index.ts`
- Modify: `src/components/chatbot/useChatSession.ts`
- Modify: `src/components/chatbot/ChatOverlay.tsx`
- Modify: `src/components/chatbot/HomeView.tsx` (hanya jika type `onOpenHistory` perlu tetap optional; sudah optional)
- Modify: `src/App.tsx`
- Modify: `src/extension/mountChatbot.ts`
- Modify: `vite.config.ts` (align the standalone preview proxy with the local backend)
- Test: `scripts/ui.test.mjs`

**Interfaces:**
- Consumes: origin/main `ChatOverlay`, `useChatSession`, `chatRequest.ts`, `index.css`, `tokens.css`, `typography.css`, `preview.css`.
- Produces:
  - `src/api/chatTransport.ts`: `type ChatTransport = (message: string, options?: { sessionId?: string; signal?: AbortSignal }) => Promise<ChatReply>`, `class ChatServiceUnavailableError`, `class ChatSessionNotFoundError`.
  - `src/api/types.ts`: `ChatSource`, `ChatReply`, `ChatSessionSummary`, `ChatSessionTurn`, `ChatSessionDetail`.
  - `src/components/chatbot/types.ts`: `ChatMessage.sources?: ChatSource[]`, `ChatHistoryItem.updatedAt?: string`.
  - `useChatSession(requestReply?: ChatTransport)` returns `{ messages, sessionId, isAssistantLoading, isHydrating, sendMessage, loadSession, resetConversation }`.
  - `ChatOverlayProps`: `{ user, suggestions, historyItems?, requestReply?, historyEnabled? }`.

- [ ] **Step 1: Copy the failing UI tests and pure ports from the local FE**

From `D:\chunking\frontend`, copy these files into the worktree, preserving paths:

```powershell
$local = 'D:\chunking\frontend'
Copy-Item "$local\scripts\ui.test.mjs" 'scripts\ui.test.mjs' -Force
Copy-Item "$local\src\api\types.ts" 'src\api\types.ts' -Force
Copy-Item "$local\src\api\mapSource.ts" 'src\api\mapSource.ts' -Force
Copy-Item "$local\src\api\client.ts" 'src\api\client.ts' -Force
Copy-Item "$local\src\api\sessionsApi.ts" 'src\api\sessionsApi.ts' -Force
Copy-Item "$local\src\lib\formatReply.ts" 'src\lib\formatReply.ts' -Force
Copy-Item "$local\src\components\chatbot\SourceList.tsx" 'src\components\chatbot\SourceList.tsx' -Force
Copy-Item "$local\src\components\chatbot\types.ts" 'src\components\chatbot\types.ts' -Force
Copy-Item "$local\src\components\chatbot\MessageBubble.tsx" 'src\components\chatbot\MessageBubble.tsx' -Force
Copy-Item "$local\src\components\chatbot\MessageList.tsx" 'src\components\chatbot\MessageList.tsx' -Force
Copy-Item "$local\src\components\chatbot\HistoryView.tsx" 'src\components\chatbot\HistoryView.tsx' -Force
Copy-Item "$local\src\components\chatbot\index.ts" 'src\components\chatbot\index.ts' -Force
Copy-Item "$local\src\components\chatbot\useChatSession.ts" 'src\components\chatbot\useChatSession.ts' -Force
Copy-Item "$local\src\components\chatbot\ChatOverlay.tsx" 'src\components\chatbot\ChatOverlay.tsx' -Force
Copy-Item "$local\src\App.tsx" 'src\App.tsx' -Force
Copy-Item "$local\src\api\chatApi.ts" 'src\api\chatApi.ts' -Force
```

Do **not** copy `src/index.css`, `src/preview.css`, `src/main.tsx`, `src/design-system/tokens.css`, or `src/design-system/typography.css`. Keep the origin/main versions because they contain `:host` selectors and the preview/extension CSS split.

- [ ] **Step 2: Run the UI tests and confirm the new expectations fail**

Run: `npm test`

Expected: failures in the copied `scripts/ui.test.mjs` for source cards, `stripSourceBlock`, chat API, sessions API, and history loading/error states. Existing extension tests still run and may pass or fail only because `ChatOverlay`/`useChatSession` are now the local versions.

- [ ] **Step 3: Add the shared transport types**

Create `src/api/chatTransport.ts`:

```ts
import type { ChatReply } from './types'

export type ChatTransport = (
  message: string,
  options?: { sessionId?: string; signal?: AbortSignal },
) => Promise<ChatReply>

export class ChatServiceUnavailableError extends Error {
  constructor() {
    super('Chat service is not configured')
    this.name = 'ChatServiceUnavailableError'
  }
}

export class ChatSessionNotFoundError extends Error {
  constructor() {
    super('Chat session no longer exists')
    this.name = 'ChatSessionNotFoundError'
  }
}
```

Modify `src/api/chatRequest.ts` only enough to share the existing error class: remove the local `ChatServiceUnavailableError` class, import it from `./chatTransport`, and re-export it so the old extension tests keep importing it from `chatRequest.ts`. Leave `requestChatReply` and the old string-returning `ChatTransport` type in place until Task 2.

- [ ] **Step 4: Make the preview chat client produce `ChatReply`**

Update `src/api/chatApi.ts` so `sendChatMessage` is typed as the new `ChatTransport`:

- Parse `session_id`, `reply`, `reply_format`, and `sources` exactly as the local FE did.
- On `ApiError` with `status === 404` **and** a non-empty `options.sessionId`, throw `ChatSessionNotFoundError`.
- Re-throw all other errors unchanged so status/code/retryAfterS remain available to the preview UI.
- `sendChatMessage('Halo', { sessionId: 'sess-0' })` must serialize `{ message: 'Halo', session_id: 'sess-0' }`.

Also align the standalone preview proxy with the local backend by copying `D:\chunking\frontend\vite.config.ts`: it targets `http://127.0.0.1:8001`, keeps the `/api` prefix (no `rewrite`), and uses the same proxy for `server` and `preview`. The old `origin/main` config targets `127.0.0.1:8000` and strips `/api`, which 404s against the real local backend.

- [ ] **Step 5: Merge `useChatSession` with transport injection**

Start from the copied local file and change only these parts:

```ts
import { ChatSessionNotFoundError } from '../../api/chatTransport'
import type { ChatTransport } from '../../api/chatTransport'

export function useChatSession(requestReply: ChatTransport = sendChatMessage) {
  // ...
}
```

Replace every `sendChatMessage(text, { ... })` call with `requestReply(text, { ... })`. Replace the 404 branch:

```ts
if (sessionId && error instanceof ChatSessionNotFoundError) {
  setSessionId(null)
  reply = await requestReply(text, { signal: controller.signal })
} else {
  throw error
}
```

Keep `getSession`, `loadSession`, `isHydrating`, and `resetConversation` because the Vite preview still uses server history.

- [ ] **Step 6: Merge `ChatOverlay` with `requestReply` and `historyEnabled`**

Start from the copied local file and make these exact changes:

- Extend props:

```ts
import type { ChatTransport } from '../../api/chatTransport'

export interface ChatOverlayProps {
  user: ChatUser
  suggestions: string[]
  historyItems?: ChatHistoryItem[]
  requestReply?: ChatTransport
  /** Preview defaults to true; the extension passes false. */
  historyEnabled?: boolean
}
```

- Destructure `historyEnabled = true` and call `useChatSession(requestReply)`.
- In `openHistory`, return immediately when `!historyEnabled`; otherwise keep the local `listSessions()` loading logic.
- Render `HistoryView` only when `historyEnabled && view === 'history'`.
- Pass `onOpenHistory={historyEnabled ? openHistory : undefined}` to `HomeView` and `ConversationView`.
- Keep origin/main's shadow-root-aware Escape and focus effects (the ones using `panelRef.current?.getRootNode()` and `ShadowRoot`), not the local `document` versions.

- [ ] **Step 7: Wire the extension to the old transport temporarily**

Modify `src/extension/mountChatbot.ts`:

```ts
import type { ChatTransport } from '../api/chatTransport'

const temporaryTransport: ChatTransport = async (message, options) => ({
  sessionId: '',
  reply: await sendExtensionChatMessage(message, options?.signal),
  replyFormat: 'markdown',
  sources: [],
})
```

Pass `requestReply: temporaryTransport` and `historyItems: []` to `ChatOverlay`. Do **not** pass `historyEnabled: false` yet; the existing browser test still opens the empty History view. This adapter is temporary and is removed in Task 2.

- [ ] **Step 8: Run the tests, typecheck, lint, and both builds**

Run:

```powershell
npm test
npm run typecheck
npm run lint
npm run build
npm run build:web
```

Expected: all pass. `npm test` includes the copied UI tests and the unchanged extension tests. If `src/api/chatApi.ts` still imports `requestJson` and `ApiError`, that is expected at this stage; Task 2 replaces it.

- [ ] **Step 9: Commit**

```bash
git add src scripts/ui.test.mjs
git commit -m "feat: adopt local chat UI with sources and sessions"
```

---

### Task 2: Sambungkan bridge extension ke API sesi dan sources

**Files:**
- Modify: `src/api/chatRequest.ts`
- Modify: `src/api/chatApi.ts`
- Modify: `src/extension/chatProtocol.ts`
- Modify: `src/extension/chatTransport.ts`
- Modify: `src/extension/handleChatPort.ts`
- Modify: `src/extension/mountChatbot.ts`
- Modify: `scripts/extension.test.mjs`
- Modify: `scripts/browser.test.mjs`
- Test: `scripts/extension.test.mjs`, `scripts/browser.test.mjs`

**Interfaces:**
- Consumes: Task 1 `ChatTransport`, `ChatReply`, `ChatSource`, `ChatSessionNotFoundError`, `ChatServiceUnavailableError`, `ChatOverlay` with `historyEnabled`.
- Produces:
  - `requestChatReply({ endpoint, message, sessionId?, signal?, timeoutMs? }): Promise<ChatReply>`.
  - `ChatPortRequest { type: 'chat'; message: string; sessionId?: string }`.
  - `ChatPortResponse` success: `{ ok: true; sessionId: string; reply: string; replyFormat: string; sources: unknown[] }`.
  - `ChatPortResponse` failure: `{ ok: false; code: 'unavailable' | 'failed' | 'invalid' | 'session_not_found' }`.

- [ ] **Step 1: Write the failing extension tests**

Update `scripts/extension.test.mjs` so its mock server reads `{ message, session_id }` and records both. Load `requestChatReply` from `/src/api/chatRequest.ts`, and load `ChatServiceUnavailableError` plus `ChatSessionNotFoundError` from `/src/api/chatTransport.ts`. Add these tests:

```js
test('HTTP adapter returns session ids, Markdown format and mapped sources', async () => {
  const reply = await requestChatReply({ endpoint, message: 'data' })
  assert.equal(reply.sessionId, 'new-session')
  assert.equal(reply.reply, 'Reply to data')
  assert.equal(reply.replyFormat, 'markdown')
  assert.equal(reply.sources.length, 1)
  assert.equal(reply.sources[0].sliceId, '1')
  assert.equal(reply.sources[0].rowsCovered, '1 of 1')
})

test('HTTP adapter forwards an existing session id', async () => {
  await requestChatReply({ endpoint, message: 'again', sessionId: 'old-session' })
  assert.equal(received.at(-1).sessionId, 'old-session')
})

test('HTTP adapter distinguishes an expired session from a generic 404', async () => {
  await assert.rejects(
    requestChatReply({ endpoint, message: 'expired', sessionId: 'old-session' }),
    ChatSessionNotFoundError,
  )
  await assert.rejects(requestChatReply({ endpoint, message: 'expired' }))
})

test('HTTP adapter drops malformed source entries', async () => {
  const reply = await requestChatReply({ endpoint, message: 'malformed-sources' })
  assert.equal(reply.sources.length, 1)
  assert.equal(reply.sources[0].chart, 'Chart')
})
```

Add a `malformed-sources` branch to the mock server:

```js
if (message === 'malformed-sources') {
  res.end(JSON.stringify({
    session_id: 's1',
    reply: 'ok',
    reply_format: 'markdown',
    sources: [null, {}, { chart: 'Chart', relevance: 0.5 }],
  }))
  return
}
```

Update the worker expectations:

```js
assert.deepEqual(port.responses, [{
  ok: true,
  sessionId: 'new-session',
  reply: 'Reply to once',
  replyFormat: 'markdown',
  sources: [{
    dashboard: 'Dashboard',
    chart: 'Chart',
    sliceId: '1',
    rowsCovered: '1 of 1',
    dataAsOf: '2026-10-06',
    possiblyOutdated: true,
    relevance: 0.9,
    content: 'x',
  }],
}])
```

Add a worker test:

```js
test('worker returns session_not_found for an expired session', async () => {
  const port = fakePort()
  handleChatPort(port, endpoint)
  port.send({ type: 'chat', message: 'expired', sessionId: 'old-session' })
  await waitFor(() => port.responses.length === 1)
  assert.deepEqual(port.responses, [{ ok: false, code: 'session_not_found' }])
})
```

Add invalid session-id cases to the existing invalid-payload test:

```js
{ type: 'chat', message: 'x', sessionId: 'has space' },
{ type: 'chat', message: 'x', sessionId: 'x'.repeat(65) },
{ type: 'chat', message: 'x', sessionId: 42 },
```

Update the mock server in `scripts/browser.test.mjs`. Add `beforeEach` to the `node:test` import and reset the request log and session counter before every test so session ids are deterministic:

```js
import { after, before, beforeEach, test } from 'node:test'
// ...
beforeEach(() => { received.length = 0; sessionCounter = 0 })
```

Then replace the response logic:

```js
const sources = [{
  dashboard: 'Dashboard Koperasi',
  chart: 'Jumlah Koperasi',
  slice_id: '608',
  rows_covered: '1 of 1',
  data_as_of: '2026-10-06T04:36:00+00:00',
  possibly_outdated: false,
  relevance: 0.9,
  content: 'x',
}]
let sessionCounter = 0

const body = JSON.parse(bodyText || '{}')
received.push({ message: body.message, sessionId: body.session_id, method: req.method, cookie: req.headers.cookie })
res.setHeader('Content-Type', 'application/json')
if (body.message === 'status') { res.writeHead(503).end('{}'); return }
if (body.message === 'expired' && body.session_id) {
  res.writeHead(404).end('{"detail":"session not found"}')
  return
}
if (body.message === 'slow') {
  const timer = setTimeout(() => res.end(JSON.stringify({
    session_id: body.session_id ?? `s${++sessionCounter}`,
    reply: answer,
    reply_format: 'markdown',
    sources,
  })), 1500)
  res.on('close', () => { clearTimeout(timer); if (!res.writableEnded) cancelled++ })
  return
}
res.end(JSON.stringify({
  session_id: body.session_id ?? `s${++sessionCounter}`,
  reply: answer,
  reply_format: 'markdown',
  sources,
}))
```

Use this `answer` so the plain-text source block must be stripped:

```js
const answer = '**Data DIY**\n\n| Wilayah | Jumlah |\n| --- | --- |\n| DIY | 42 |\n\nSumber:\n- Dashboard Koperasi — Jumlah Koperasi (baris 1 of 1)'
```

Update the browser tests:

- Remove the history-button interaction from the Shadow DOM test. Assert `page.getByRole('button', { name: 'Riwayat chat' }).count() === 0` and collect `/api/sessions` requests; assert none occurred.
- In the configured test, after the first message assert the Markdown table, `Sumber`, `Dashboard Koperasi — Jumlah Koperasi`, and that `Sumber:` is absent. Assert the first request has `sessionId: undefined`.
- Send a second message and assert `received.at(-1).sessionId` equals the first response's session id (`s1`).
- Add an expired-session test: send `first`, wait for the reply, send `expired`, wait for two `expired` requests, assert the first has `sessionId: 's1'` and the retry has `sessionId: undefined`; assert the reply renders.
- Keep placeholder, draft, cancellation, backend failure, viewport, and other-origin tests; update only the contract-dependent assertions.

- [ ] **Step 2: Run the unit tests and confirm they fail**

Run: `npm test`

Expected: failures because `requestChatReply` still returns a string, the port protocol has no `sessionId`/`sources`, and the worker does not return `session_not_found`.

- [ ] **Step 3: Rewrite `requestChatReply` to return `ChatReply`**

In `src/api/chatRequest.ts`:

```ts
import { mapSource } from './mapSource'
import { ChatServiceUnavailableError, ChatSessionNotFoundError } from './chatTransport'
import type { ChatReply, ChatSource } from './types'

export interface ChatRequestOptions {
  endpoint: string
  message: string
  sessionId?: string
  signal?: AbortSignal
  timeoutMs?: number
}

export class ChatRequestError extends Error {
  readonly status: number
  readonly code?: string
  readonly retryAfterS?: number
  // constructor sets name = 'ChatRequestError'
}

export async function requestChatReply(options: ChatRequestOptions): Promise<ChatReply>
```

Behavior:

- `signal?.throwIfAborted()` first.
- Blank endpoint -> `ChatServiceUnavailableError`.
- Default timeout 60.000 ms; combine caller signal with `AbortSignal.any`.
- POST JSON `{ message, session_id? }`; `credentials: 'omit'`, `redirect: 'error'`.
- 404 with non-empty `sessionId` -> `ChatSessionNotFoundError`.
- Other non-2xx -> `ChatRequestError` with `status`, optional `code`, optional `retryAfterS` parsed from `{ detail, code, retry_after_s }`.
- 2xx body must be an object with a non-empty string `reply`; else `Error`.
- Map `session_id` to `sessionId` (default `''`), `reply_format` to `replyFormat` (default `markdown`), and `sources` through `mapSource`, dropping `null` and entries that have neither `dashboard` nor `chart`.
- Remove the old string-returning `ChatTransport` type from this file; import/re-export the new one from `./chatTransport` only if another module still needs it.

- [ ] **Step 4: Delegate the preview client to `requestChatReply`**

Replace `src/api/chatApi.ts` with:

```ts
import { requestChatReply } from './chatRequest'
import type { ChatTransport } from './chatTransport'

export const sendChatMessage: ChatTransport = (message, options = {}) =>
  requestChatReply({
    endpoint: '/api/chat',
    message,
    sessionId: options.sessionId,
    signal: options.signal,
  })
```

- [ ] **Step 5: Extend the port protocol**

In `src/extension/chatProtocol.ts`:

```ts
export const MAX_SESSION_ID_LENGTH = 64
const SESSION_ID_PATTERN = /^[A-Za-z0-9_-]+$/

export interface ChatPortRequest {
  type: 'chat'
  message: string
  sessionId?: string
}

export type ChatPortResponse =
  | { ok: true; sessionId: string; reply: string; replyFormat: string; sources: unknown[] }
  | { ok: false; code: 'unavailable' | 'failed' | 'invalid' | 'session_not_found' }
```

- `isChatPortRequest` keeps the non-empty/20.000-character message rules and adds: if `sessionId` is present and not `undefined`, it must be a string of length 1–64 matching `^[A-Za-z0-9_-]+$`.
- `isChatPortResponse` success requires string `sessionId`, non-empty string `reply`, string `replyFormat`, and `Array.isArray(sources)`.
- Failure code list adds `session_not_found`.

- [ ] **Step 6: Forward sessions through the worker**

In `src/extension/handleChatPort.ts`:

```ts
import { ChatServiceUnavailableError, ChatSessionNotFoundError } from '../api/chatTransport'
import { requestChatReply } from '../api/chatRequest'

void requestChatReply({
  endpoint,
  message: value.message.trim(),
  sessionId: value.sessionId,
  signal: controller.signal,
  timeoutMs: WORKER_REQUEST_TIMEOUT_MS,
}).then(
  reply => respond({
    ok: true,
    sessionId: reply.sessionId,
    reply: reply.reply,
    replyFormat: reply.replyFormat,
    sources: reply.sources,
  }),
  error => {
    if (error instanceof ChatSessionNotFoundError) respond({ ok: false, code: 'session_not_found' })
    else if (error instanceof ChatServiceUnavailableError) respond({ ok: false, code: 'unavailable' })
    else respond({ ok: false, code: 'failed' })
  },
)
```

Keep the synchronous listener, sender validation, one-request-per-port rule, and abort-on-disconnect.

- [ ] **Step 7: Extend the content transport**

In `src/extension/chatTransport.ts`:

- Import `ChatSessionNotFoundError`, `ChatServiceUnavailableError`, and `ChatTransport` from `../api/chatTransport`; import `ChatSource` from `../api/types`.
- Signature becomes the Task 1 `ChatTransport`.
- Include `sessionId` in the posted request only when truthy.
- Success response resolves `{ sessionId, reply, replyFormat, sources: sources as ChatSource[] }`.
- `unavailable` -> `ChatServiceUnavailableError`.
- `session_not_found` -> `ChatSessionNotFoundError`.
- Keep the 30-second client watchdog, abort listener, disconnect handling, and `port.disconnect()` cleanup.

- [ ] **Step 8: Remove the temporary adapter and hide History**

In `src/extension/mountChatbot.ts`, delete `temporaryTransport`, pass `requestReply: sendExtensionChatMessage`, and pass `historyEnabled: false`. Remove `historyItems: []` if it is no longer needed. `ChatOverlay` must not render the History button or call `listSessions` in the extension.

- [ ] **Step 9: Run unit tests, typecheck, lint, and build**

Run:

```powershell
npm test
npm run typecheck
npm run lint
npm run build
```

Expected: all pass. Unit tests cover the new request/response contract and worker codes.

- [ ] **Step 10: Run the real Chromium extension tests**

Run:

```powershell
npx playwright install chromium
npm run test:browser
```

Expected: all browser tests pass. The test build uses `http://127.0.0.1:<port>/chat`; the production build remains unconfigured and grants no API host permission. Screenshots are written under `.output/qa/`.

- [ ] **Step 11: Commit**

```bash
git add src scripts/extension.test.mjs scripts/browser.test.mjs
git commit -m "feat: connect extension to session-aware RAG API"
```

---

### Task 3: Documentation, local backend smoke test, and branch handoff

**Files:**
- Modify: `.env.example`
- Modify: `README.md`
- Modify: `docs/AI_HANDOFF.md`
- Modify: `docs/features/extension-api.md`
- Modify: `docs/features/README.md` (only if its “next features” text is now false)
- Modify: `docs/EXTENSION_VALIDATION.md`
- Test: full command matrix + local backend smoke test

**Interfaces:**
- Consumes: Task 2 extension contract and commands.
- Produces: accurate operator documentation and a pushed feature branch.

- [ ] **Step 1: Update `.env.example`**

Use the full chat endpoint at `/api/chat`:

```dotenv
# Full chat endpoint. Leave blank to ship the "service unavailable" placeholder.
# Development may use loopback HTTP; production must be HTTPS.
WXT_CHAT_API_URL=
# WXT_CHAT_API_URL=http://127.0.0.1:8001/api/chat
```

- [ ] **Step 2: Update README**

Replace the placeholder/backend sections with:

- Extension now sends `{ message, session_id? }` and renders `{ reply, reply_format, sources }`.
- Follow-up turns reuse `session_id`; History is intentionally hidden because the backend session list is global and unauthenticated.
- `WXT_CHAT_API_URL` examples for local and production.
- Commands: `npm run build`, dev build `npx wxt build --mode development`, `npm run test:browser`.
- Note that the standalone preview still uses server history via `/api/sessions`.

- [ ] **Step 3: Update AI handoff and feature docs**

In `docs/AI_HANDOFF.md` and `docs/features/extension-api.md`, document:

```http
POST <WXT_CHAT_API_URL>
{"message":"...","session_id":"optional"}

{"session_id":"...","reply":"...","reply_format":"markdown","sources":[...]}
```

- 404 with a supplied session id causes one transparent retry without it.
- 25-second worker / 30-second client boundary; streaming remains a separate feature.
- No cookies, redirects, arbitrary URLs, or provider keys.
- `sources` are mapped from snake_case; malformed items are dropped.

- [ ] **Step 4: Update validation record**

After running the commands, write the real counts and dates into `docs/EXTENSION_VALIDATION.md`. Do not copy stale counts. Include the local backend smoke result and note whether the live portal was manually checked.

- [ ] **Step 5: Run the full verification matrix**

```powershell
npm run lint
npm run typecheck
npm test
npm run build
npm run build:web
npm run test:browser
```

Expected: all pass. Record the exact test counts and any skipped/unavailable checks.

- [ ] **Step 6: Smoke-test against the real local backend**

Start the backend in a separate terminal:

```powershell
cd D:\chunking\backend
py -m uvicorn rag.web.app:app --host 127.0.0.1 --port 8001
```

Check the contract directly:

```powershell
$body = @{ message = 'Berapa jumlah koperasi di DIY?' } | ConvertTo-Json
$reply = Invoke-RestMethod -Uri 'http://127.0.0.1:8001/api/chat' -Method Post -ContentType 'application/json' -Body $body
$reply.session_id
$reply.reply_format
$reply.sources.Count
```

Expected: a non-empty `session_id`, `reply_format = markdown`, and a numeric source count.

Then build the development extension with the local endpoint:

```powershell
$env:WXT_CHAT_API_URL = 'http://127.0.0.1:8001/api/chat'
npx wxt build --mode development
```

Load `.output/chrome-mv3-dev` in Chromium, open `https://idmc.jogjaprov.go.id/`, and verify one question plus one follow-up. If the environment has no GUI or network access to the portal, record that the browser smoke test was not performed and rely on `npm run test:browser`; do not claim it passed.

- [ ] **Step 7: Commit and push**

```bash
git add .env.example README.md docs
git commit -m "docs: document connected extension backend"
git push -u origin feature/local-fe-extension
```

Report the branch name, commit list, test results, and the compare URL. Do not merge into `main`.
