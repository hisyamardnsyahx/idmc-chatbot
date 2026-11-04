# IDMC Chatbot Frontend

Chat overlay for the IDMC / Portal Data Publik DIY RAG chatbot. The UI talks to
the backend over `/api` and renders Markdown replies with structured source
cards and server-backed session history.

**Project root**
`D:\chunking\frontend`

**Figma**
https://www.figma.com/design/xN5zluS2lWIxKY4VwZXMHL/Frontend-Dev-IDMC-Chatbot?node-id=0-1&p=f&t=w1S0htUCnyRUayeD-0

The Figma HiFi remains the visual source of truth. Do not redesign it, and do
not implement the sidebar.

## Stack

- Vite
- React 19
- TypeScript
- Tailwind CSS 4 (via `@tailwindcss/vite`) plus scoped CSS tokens
- ESLint
- `react-markdown` + `remark-gfm`

Keep dependencies minimal. Do not add a router, Redux/Zustand, or UI component
libraries unless explicitly requested.

## Features

- Floating launcher and chat overlay over a host dashboard page.
- Home state with greeting and suggestion chips.
- Conversation state with user/assistant bubbles and a typing indicator.
- Assistant replies rendered as Markdown (GFM tables included).
- Source cards built from the `sources` array returned by `POST /api/chat`;
  stale/partial notes stay visible.
- Session history: `GET /api/sessions` lists sessions and selecting one loads
  its turns via `GET /api/sessions/{id}`.
- Session 404 recovery: a deleted server session restarts transparently with
  one retry.
- API errors render as an in-chat error state instead of crashing.

No authentication and no client-side persistence of chat history; history lives
on the backend.

## Run

Start the backend first from `D:\chunking\backend`:

```powershell
py -m uvicorn rag.web.app:app --host 127.0.0.1 --port 8001
```

Then, from `D:\chunking\frontend`:

```powershell
npm ci
npm run dev
```

Open `http://localhost:5173`. Vite proxies `/api` to
`http://127.0.0.1:8001` (see `vite.config.ts`); `127.0.0.1` avoids Node
resolving to `::1` while uvicorn listens on IPv4. `npm run preview` serves on
port 4173 with the same proxy.

## Scripts

```powershell
npm run test        # node --test scripts/ui.test.mjs
npm run typecheck   # tsc -b --pretty false
npm run lint        # eslint .
npm run build       # tsc -b && vite build
npm run dev         # vite
npm run preview     # vite preview
```

Last recorded frontend run: 17 tests passed, typecheck/lint/build passed.
Task 9 re-runs them.

## Structure

```text
src/
├─ api/               chat + sessions clients, types, source mapping
├─ components/chatbot/ overlay, home/conversation/history views, sources
├─ design-system/     tokens and typography CSS
├─ lib/               small utilities
├─ App.tsx            local host-page preview
└─ main.tsx
```

`App.tsx` is a local showcase over an empty host page, not the production
embedding architecture. Shadow DOM / dashboard injection is not implemented.

## Backend contract

- `POST /api/chat` — `{message, session_id?, dashboard_name?, top_k?}` →
  `{session_id, reply, reply_format, sources}`
- `GET /api/sessions`, `GET /api/sessions/{id}`
- `DELETE /api/sessions/{id}` exists in the backend, but the UI intentionally
  has no delete button yet.

Full runbook: `D:\chunking\docs\INTEGRATION.md`.
