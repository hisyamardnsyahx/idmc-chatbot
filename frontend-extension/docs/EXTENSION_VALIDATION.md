# Extension validation

Validated on 2026-11-03 (Asia/Jakarta), using Node 22.22.2, npm 10.9.7,
WXT 0.21.5, Vite 8.3.5 and Playwright 1.62.1 with its Chromium runtime.

## Automated matrix

| Check | Result |
| --- | --- |
| `npm run lint` | Passed |
| `npm run typecheck` | Passed (also part of production build) |
| `npm test` | 32 passed: 18 UI/API tests and 14 extension/worker/configuration tests |
| `npm run test:browser` | 10 passed with actual compiled Manifest V3 extensions |
| `npm run build` | Passed; `.output/chrome-mv3` |
| `npm run build:web` | Passed; original Vite preview in `dist` |
| Development build with local endpoint | Passed; `.output/chrome-mv3-dev`, host permission `http://127.0.0.1/*`, content script limited to `https://idmc.jogjaprov.go.id/*` |

Browser fixtures are served at `https://idmc.jogjaprov.go.id/` with deliberately
conflicting global button styles, a different root font size and nonzero body margin.
They verify actual manifest-based injection, Shadow DOM isolation, pointer input,
keyboard focus/Escape, placeholder errors, cross-origin background requests,
Markdown replies, structured source cards with the plain-text `Sumber:` block
stripped, session-id reuse on the second turn, one transparent retry after an
expired-session 404, hidden History (no History button and no `/api/sessions`
request), pending drafts, duplicate-submit protection and cancellation.
Viewport checks cover 1280x900, 390x844, 320x568 and 844x390. Other origins and
same-origin subframes receive no extension UI.

The backend URL is blank in the production output. Only the separate test build
uses a temporary local mock server; the production artifact still grants no API host
permission. Screenshots are generated in `.output/qa/`.

## Local backend smoke test

The real backend was started with
`py -m uvicorn rag.web.app:app --host 127.0.0.1 --port 8001` from `D:\chunking\backend`.
The local `.env` was pointed at the Kenari endpoint for this validation; the API key
stays outside the repository and the extension.

| Check | Result |
| --- | --- |
| `GET /api/health` | 200, `{"status":"ok"}` |
| `GET /api/stats` | 507 indexed chunks; provider `openai-compat`; model `deepseek-v4-1-flash` |
| `POST /api/search` | 200 in 3.93 s with 5 results |
| `POST /api/chat` (first request after backend start) | 200 in 24.83 s; `session_id`, Markdown reply and 10 sources |
| `POST /api/chat` (fresh session) | 200 in 9.29 s; Markdown reply and 5 sources |
| `POST /api/chat` (follow-up, same session) | 200 in 3.68 s; retained the first question; no new retrieval sources |
| Live extension, first run | 9.67 s; reply rendered with a source card; no page errors |
| Live extension, two-turn run | 4.75 s then 3.96 s; follow-up identified the first question; no page errors |

The first request after process start took 24.83 s, only 0.17 s below the 25-second
worker boundary. Subsequent requests were 3.68-9.67 s. The cold-start margin remains
a deployment risk and should be watched, but it did not fail during this run. The
model id was confirmed through `/v1/models`; the prefixed form
`kenari/deepseek-v4-1-flash` was rejected with `400 model_not_found`. No streaming,
timeout increase or hidden retry was added.

## Scope note

No backend source code, model configuration or API keys were committed. The local
`.env` was switched to Kenari only for this smoke test; the key remains outside the
repository and extension. The local backend process was stopped after validation.
Production remains unconfigured in the built extension until an HTTPS
`WXT_CHAT_API_URL` is supplied at build time.
