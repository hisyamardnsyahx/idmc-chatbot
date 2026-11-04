# Feature branches

The three original migration features are merged into `main`. Their separate branches
and commits are retained for documentation. They were implemented and merged in the
dependency order shown below.

The current integration branch, `feature/local-fe-extension`, is based on `origin/main`
and ports the local frontend plus the session-aware RAG connection. It is not merged
into `main`; use that branch to run the connected extension.

| Branch | Original base | Documentation |
| --- | --- | --- |
| `feature/wxt-foundation` | `main` | [WXT foundation](wxt-foundation.md) |
| `feature/extension-overlay` | `feature/wxt-foundation` | [Portal overlay](extension-overlay.md) |
| `feature/extension-api` | `feature/extension-overlay` | [API bridge](extension-api.md) |
| `feature/local-fe-extension` | `origin/main` | [API bridge](extension-api.md) |

Use `main` for the placeholder-API extension and `feature/local-fe-extension` for the
connected extension. New independent features should start from updated `main` using a
new `feature/` branch; do not append unrelated work to these completed migration
branches. Frontend visual changes should be agreed with the UI/UX designer before
implementation.

For each feature, document the user-visible result, scope, architecture decisions,
configuration and validation. Keep screenshots, dependency caches and unpacked
extension output out of Git. Push branches and create PRs when ready for team review;
branch creation and local commits do not publish them automatically.
