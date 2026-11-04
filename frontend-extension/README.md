# IDMC Chatbot Browser Extension

React + TypeScript + Tailwind chatbot, packaged with WXT as a Chromium Manifest V3
extension for **https://idmc.jogjaprov.go.id/**. The original Figma widget design
and standalone Vite preview are retained.

## Requirements

- Node.js 22 or newer and npm.
- Chrome or Microsoft Edge 120 or newer.

## Install and try

```powershell
npm ci
npm run build
```

Open `chrome://extensions` or `edge://extensions`, enable Developer mode, choose
**Load unpacked**, and select `.output/chrome-mv3`. Refresh an IDMC portal tab.
The floating launcher appears at the bottom right. Only the exact HTTPS hostname
is matched, in the top frame; other sites, HTTP URLs and subdomains are excluded.

The extension is connected to the session-aware RAG contract. It sends
`{ "message": "...", "session_id": "..." }` and renders
`{ "session_id": "...", "reply": "...", "reply_format": "markdown", "sources": [...] }`.
Follow-up turns reuse the returned `session_id`; if the server reports the session
missing (404), one transparent retry starts a fresh session. History is intentionally
hidden in the extension because the backend session list is global and unauthenticated.
The standalone Vite preview still uses server history via `/api/sessions`.

With `WXT_CHAT_API_URL` blank, the build ships a safe placeholder: sending a question
shows a service-unavailable message and no backend request is made.

## Development and builds

| Command | Purpose |
| --- | --- |
| `npm run dev` | WXT development/reload workflow for Chrome |
| `npm run dev:edge` | WXT development workflow targeting Edge |
| `npm run build` | Typecheck and build `.output/chrome-mv3` |
| `npm run zip` | Build and create an extension ZIP in `.output` |
| `npm run dev:web` | Original standalone Vite preview |
| `npm run build:web` | Build the standalone preview to `dist` |
| `npm run preview:web` | Serve the built standalone preview |
| `npm run lint` | ESLint |
| `npm run typecheck` | Generate WXT types and check app/config types |
| `npm test` | UI and extension API tests |
| `npm run test:browser` | Build and test real extensions with a local mock |

For browser tests, install the matching Chromium runtime once with
`npx playwright install chromium`. The test uses temporary isolated profiles and
does not install anything in your everyday browser profile. Screenshots are saved
under `.output/qa`. Automated portal fixtures verify isolation; they do not replace
a manual check against the live portal.

## Backend configuration

```powershell
Copy-Item .env.example .env.local
```

Set `WXT_CHAT_API_URL` to the **full chat endpoint**, including `/api/chat`, then
rebuild and reload. Examples:

```dotenv
# Local development (loopback HTTP is allowed only in development/test builds)
WXT_CHAT_API_URL=http://127.0.0.1:8001/api/chat
# Production
WXT_CHAT_API_URL=https://rag.example.org/api/chat
```

Production requires HTTPS. Build the development extension with:

```powershell
$env:WXT_CHAT_API_URL = 'http://127.0.0.1:8001/api/chat'
npx wxt build --mode development
```

Then load `.output/chrome-mv3-dev`. For the production bundle and automated extension
tests use `npm run build` and `npm run test:browser`. If the URL is blank, the
extension stays in the placeholder state and grants no API host permission.

The extension fetches through its background worker using narrowly scoped host
permissions. It sends no cookies and rejects redirects. Its request timeout is 25
seconds; slower RAG responses need an agreed streaming/job API. Never bundle model
provider keys in `WXT_` variables. See [AI handoff](docs/AI_HANDOFF.md) and
[API feature](docs/features/extension-api.md).

The Vite preview separately retains `/api/chat` proxied to
`http://127.0.0.1:8001/api/chat` and still uses server history through
`/api/sessions`.

## Architecture

- `wxt.config.ts`: extension configuration, React/Tailwind and API host permission.
- `src/entrypoints/chatbot.content.ts`: scoped portal injection and Shadow DOM lifecycle.
- `src/entrypoints/background.ts`: validated, cancelable chat requests.
- `src/extension/`: mount, isolated styles/fonts and runtime messaging.
- `src/components/chatbot/`: existing Home, Conversation and History components.
- `src/api/`: shared HTTP adapter and preview transport.
- `src/App.tsx`, `src/main.tsx`, `vite.config.ts`: standalone development preview.

Fonts and icons are bundled locally. The extension does not scrape portal data,
read portal authentication or persist chats. Only submitted questions are sent to
the configured backend. History is intentionally hidden in the extension; closing
the panel clears the current conversation. The standalone preview keeps server
history. Authentication, streaming and Firefox support remain separate features.

## Feature documentation

Use the complete extension from `main`. The migration retains separate
`feature/wxt-foundation`, `feature/extension-overlay` and `feature/extension-api`
branches and commits; see [feature index](docs/features/README.md) for migration history.

Styling rules remain in [styling architecture](docs/STYLING_ARCHITECTURE.md).
The original [frontend polish](docs/FRONTEND_POLISH.md) is historical validation;
extension-specific behavior is described in the feature docs.

Design source: [Figma frontend](https://www.figma.com/design/xN5zluS2lWIxKY4VwZXMHL/Frontend-Dev-IDMC-Chatbot?node-id=0-1).
