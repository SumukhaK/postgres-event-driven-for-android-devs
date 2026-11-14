# Implementation Plan: Developer Studio learning platform

## Overview

Build a runnable learning product around the existing PostgreSQL course. Keep course content as the source of truth, add browser-side PostgreSQL practice, account-backed progress, graduated help, and optional user-connected AI providers. The first completion target is a documented local deployment; public hosting needs a separate backend host and credentials.

## Architecture decisions

- A separate FastAPI service owns course accounts, sessions, progress, provider credentials, and static app serving. The ChaiPoint sample API stays separate.
- PGlite runs learner SQL in the browser and persists its sandbox in IndexedDB. Query execution is never sent to the service database.
- SQLite is the smallest durable learning-account store for local/single-instance deployment; configure a persistent path for hosted use.
- Provider credentials are user supplied and encrypted at rest. Support OpenAI API, Anthropic Console API, and OpenCode Console API. OpenAI SIWC plan usage is opt-in and local-runtime-only; Claude consumer subscription OAuth is not supported.
- Retain the GitHub Pages tutorial build and include a container-based path for the full-stack app.

## Task List

See `tasks/todo.md` for the live task tracker and acceptance/verification criteria. Tasks must be completed in dependency order and checkpoints updated as work lands.

## Risks

| Risk | Impact | Mitigation |
|---|---|---|
| GitHub Pages is static only | Accounts and AI cannot run on Pages alone | Serve the same frontend from FastAPI locally and document a separate backend deployment target |
| Provider access differs by product and plan | A generic “sign in to ChatGPT/Claude” button would mislead learners | Use local SIWC only for eligible ChatGPT users, plus documented API-key routes and clear billing copy |
| SIWC token storage is restricted | Remote storage of ChatGPT plan tokens violates the local user-control requirement | Keep SIWC tokens in the user's local loopback runtime; disable the flow on remote hosts |
| SQLite is single-instance oriented | Multi-instance public deployment may lose consistency | Require persistent disk and document migration to PostgreSQL before horizontal scaling |
| PGlite adds a browser database dependency | Build size/startup and browser compatibility | Pin the package, seed only course data, and test modern browser startup/failure states |
| AI is optional and can fail | Learners could lose help or progress | Keep static hints/solutions always available and separate provider failures from progress writes |

## Completion checkpoint

- [ ] All tracker tasks and checkpoints are complete.
- [ ] Local end-to-end path is verified from clean startup through sign-up, practice, progress save, AI help (with configured credentials), and sign-in persistence.
- [ ] Existing tutorial and demo builds remain intact.
- [ ] External deployment prerequisites are listed; no live deployment is claimed without verification.
