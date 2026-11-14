# Developer Studio platform task tracker

Work each task in order. Update this file as part of the task, including verification results and blockers. Full criteria and architecture are in [`plan.md`](plan.md) and the [design spec](../docs/superpowers/specs/2026-11-14-developer-studio-platform-design.md).

## Phase 0 · Foundation

- [x] **T0 · Inspect repo and record product boundaries** — confirm course source/build, existing API, design direction, and provider constraints. **Verified:** 13 chapters + index; existing FastAPI app is only the ChaiPoint demo; OpenAI plan sharing is partner/permission gated; use Anthropic Console API, not Claude subscription OAuth.
- [x] **T1 · Create runnable app foundation** — add a separate FastAPI learning app and local run/container setup. **Accept:** one origin serves lessons and app; existing Pages build and demo API remain separate. **Verified:** `python tools/build.py` built 13 chapters + index; `python -m pytest learning_app/tests -q` passed 3 checks; live Uvicorn served health, catalog, and home on port 18765. **Note:** Docker packaging remains in T9.

## Phase 1 · Learn and practice

- [x] **T2 · Build Developer Studio course shell** — show repository lessons, course navigation, and current lesson. **Verified:** all 13 lessons are source-derived, navigable in the shell, and loaded from generated course HTML; diagrams reinitialize on navigation; API/static route checks, `node --check`, and `git diff --check` pass. Headless Edge visually checked the shell and widths 375/768/1024/1440px with no horizontal overflow.
- [x] **T3 · Bundle the browser PostgreSQL runtime** — add a pinned PGlite/Vite build and serve the built app bundle locally. **Verified:** `npm ci`, `npm run build`, and FastAPI bundle-route smoke checks pass; PGlite/WASM assets are served from the app with no runtime CDN.
- [x] **T4 · Seed and persist the learner sandbox** — create ChaiPoint PostgreSQL tables/data in PGlite and persist the local sandbox in IndexedDB. **Verified:** `npm run test:sandbox` seeded SQL, ran SELECT/UPDATE/JOIN and a syntax error, closed/reopened the IndexedDB database, and retained the updated stock; Edge browser also showed the sandbox ready after page reload.
- [x] **T5 · Add the SQL editor, results, and reset flow** — allow learner queries and render result tables/errors with a safe row cap. **Accept:** supported SQL runs in browser; reset restores seed state; the app service never executes learner SQL. **Verified:** browser SELECT showed 4 products; UPDATE returned stock 198; reload retained 198; reset restored 200. No browser console errors or failed requests. `npm run test:sandbox`, `npm run build`, and `python -m pytest learning_app/tests -q` passed.
- [ ] **T6 · Add chapter activities and graduated help** — provide one explicit activity plus nudge, hint, solution, and explanation for each core chapter. **Accept:** help is always available offline; completion is actionable and non-shaming. **Verify:** every chapter has exercise metadata and each help level is reachable.

### Checkpoint · Practice works

- [x] App starts cleanly; chapters render; browser SQL executes against PGlite; no existing course build regressions. **Verified:** 13 lessons render, SQL executes client-side, browser flow and sandbox persistence pass, existing `tools/build.py` produced 13 pages + index.

## Phase 2 · Accounts and AI

- [ ] **T7 · Add course account and progress persistence** — registration, login, logout, sessions, and per-account chapter/exercise progress. **Accept:** password/session secrets are hashed; progress survives reload and a fresh login. **Verify:** API and UI account-flow checks, including unauthorized access and ownership boundaries.
- [ ] **T8 · Add secure AI provider connections** — encrypted user credentials for OpenAI API, Anthropic Console API, and OpenCode Console API; provider status/disconnect; accurate billing disclosures. **Accept:** no plaintext fallback; static help works without provider; AI errors do not corrupt progress. **Verify:** encryption round trip, disconnect, invalid credential/provider response, and mocked assistant request.
- [ ] **T9 · Add interactive AI coach** — contextual nudge, hint, explanation, and Q&A using the active chapter and exercise. **Accept:** AI is opt-in, provider/model selection is explicit, and prompt context contains only necessary course state. **Verify:** mocked streaming/request behavior and provider errors.

## Phase 3 · Ship and verify

- [ ] **T10 · Accessibility, responsive behavior, and loading/error states** — complete keyboard, contrast, reduced-motion, and narrow-screen passes. **Verify:** keyboard walkthrough and 320/768/1024/1440 widths.
- [ ] **T11 · Production-ready local deployment and docs** — Docker Compose, persistent DB path, encryption-key setup, env template, backup/reset instructions, and backend-host requirements. **Accept:** clean checkout start-up works; docs distinguish static Pages from full-stack app. **Verify:** build and start from clean state.
- [ ] **T12 · End-to-end verification** — run focused backend/UI checks and one full learner path. **Accept:** sign up → lesson → SQL run → help → complete → logout/login → progress restored; AI path succeeds with configured mock/provider credentials. **Verify:** commands and results recorded here.

### Checkpoint · Complete

- [ ] All tasks above are complete and end-to-end verification passes.
- [ ] Public deployment is verified, or the exact missing external credentials/host setup is recorded.
