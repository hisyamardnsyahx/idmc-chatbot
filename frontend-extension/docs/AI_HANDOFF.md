# AI engineer integration handoff

The extension UI runs on `https://idmc.jogjaprov.go.id/*`. It is wired to the
session-aware RAG endpoint supplied by the backend team. `WXT_CHAT_API_URL` is blank
by default so the production build still ships the safe "service unavailable"
placeholder until an endpoint is configured.

## Contract

```http
POST <WXT_CHAT_API_URL>
Content-Type: application/json

{"message":"Data penduduk DIY","session_id":"optional"}
```

```json
{
  "session_id": "server-assigned id",
  "reply": "Assistant reply, optionally including Markdown",
  "reply_format": "markdown",
  "sources": [
    {
      "dashboard": "Dashboard Koperasi",
      "chart": "Jumlah Koperasi",
      "slice_id": "608",
      "rows_covered": "1 of 1",
      "data_as_of": "2026-10-06T04:36:00+00:00",
      "possibly_outdated": false,
      "relevance": 0.9,
      "content": "source text"
    }
  ]
}
```

- `WXT_CHAT_API_URL` is the **full chat endpoint** (for example
  `http://127.0.0.1:8001/api/chat`), not the server base URL.
- A successful response must be 2xx JSON with a non-empty string `reply`. The frontend
  maps `session_id` to `sessionId`, `reply_format` to `replyFormat`, and `sources`
  from snake_case to camelCase. Malformed source entries without `dashboard` or
  `chart` are dropped.
- The first turn sends no `session_id`. The returned id is reused for every follow-up
  turn. If the server returns 404 for a supplied session id, the UI retries exactly
  once without `session_id`; this starts a fresh session transparently.
- The extension does not show the History UI. The backend `/api/sessions` list is
  global and unauthenticated, so the injected widget intentionally hides it. The
  standalone Vite preview still uses server history through `/api/sessions`.
- The worker aborts after 25 seconds and the client watchdog disconnects after 30
  seconds. If real RAG responses routinely exceed that boundary, agree on streaming
  or a job/polling API as a separate feature. No silent streaming or automatic POST
  retry is added.
- The extension sends no portal cookies (`credentials: 'omit'`), rejects redirects,
  cannot be pointed at an arbitrary URL by the content script, and bundles no model
  provider keys. Server-side generation cancellation can use the aborted request if
  the inference stack supports it.
- Errors and malformed responses render the existing generic chat error state.

## Enable

1. Copy `.env.example` to `.env.local`.
2. Set `WXT_CHAT_API_URL` to the full endpoint, including `/api/chat` if applicable.
3. For local loopback integration:
   `$env:WXT_CHAT_API_URL='http://127.0.0.1:8001/api/chat'; npx wxt build --mode development`
   then load `.output/chrome-mv3-dev`. For production, use the HTTPS endpoint and
   `npm run build`.
4. Reload the extension, refresh the IDMC tab, and test one question plus one
   follow-up against the real server.

WXT derives the required API host permission during the build. The extension
background worker performs the cross-origin fetch; the Vite proxy applies only to
`npm run dev:web` and `npm run preview:web`. If the real response contract differs,
adapt `src/api/chatRequest.ts` and its tests on a new `feature/` branch.
