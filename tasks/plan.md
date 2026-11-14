# Implementation Plan: Developer Studio learning platform

## Overview

Build a runnable learning product around the existing PostgreSQL course. Keep course content as the source of truth, add browser-side PostgreSQL practice, account-backed progress, graduated help, and optional user-connected AI providers. The first completion target is a documented local deployment; public hosting needs a separate backend host and credentials.

## Architecture decisions

- A separate FastAPI service owns course accounts, sessions, progress, provider credentials, and static app serving. The ChaiPoint sample API stays separate.
- PGlite runs learner SQL in the browser and persists its sandbox in IndexedDB. Query execution is never sent to the service database.
- SQLite is the smallest durable learning-account store for local/single-instance deployment; configure a persistent path for hosted use.
- Provider connections use explicit authentication modes and inference adapters. API keys remain encrypted at rest. ChatGPT plan sign-in stays local-only. Add account sign-in only through provider-supported integrations; do not reuse private CLI tokens or emulate undocumented consumer-account APIs. Claude Console API keys are supported, while generic Claude.ai subscription OAuth is not assumed to be available to third-party apps.
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

## Phase 5 · Generalize AI provider connections

**Priority:** complete and verify this phase before the planned `gpt-oss:20b` playground experiment.

The product should present one provider-connection experience while keeping each provider's supported auth and inference behavior explicit. “Sign in with provider” means authorize model usage where a provider officially supports it; it does not mean use OAuth identity tokens as an undocumented inference credential. Keep API-key and local endpoint connections alongside account sign-in, show who bills usage, and report entitlement or unsupported-flow conditions clearly.

Provider feasibility from current official documentation:

- **OpenAI / ChatGPT:** retain the existing ChatGPT plan OAuth integration and OpenAI API-key option.
- **GitHub Copilot:** investigate the official Copilot SDK's user sign-in/device flow and supported request surface; only integrate through that supported SDK/API and with clear Copilot entitlement requirements.
- **Anthropic / Claude:** retain Claude Console API keys. Claude Code documents Claude Pro/Max sign-in for Claude Code, but Anthropic's general Claude API authentication docs do not define a third-party Claude.ai subscription OAuth flow. Do not extract or reuse Claude Code credentials; add subscription sign-in only if Anthropic documents/authorizes an app integration for this use.
- **OpenCode:** retain its supported Console API key/inference route. OpenCode CLI supports provider-specific OAuth integrations, but that does not automatically grant this app permission or a reusable OpenCode account inference token. Confirm an official supported API/account flow before offering “Sign in with OpenCode.”
- **Other cloud services:** add providers through the same catalog only when official API-key, OAuth/device, or cloud identity integration details and usage/billing terms are defined. Local Ollama/vLLM/OpenAI-compatible endpoints remain a separate connection type.

### Implementation order and acceptance checks

1. **Connection contract and provider catalog:** describe provider ID, display name, supported auth methods, inference protocol, model discovery, billing source, and entitlement notes as data. Preserve current clients or migrate them compatibly. Acceptance: the UI can render supported methods from the catalog; auth mode is persisted with the encrypted connection; old connections remain usable.
2. **Official account adapters:** preserve ChatGPT sign-in; implement GitHub Copilot sign-in only if the official SDK/API fits the app's local-server architecture. Acceptance: OAuth/device state, token refresh/expiry, disconnect/revoke, account switching, and entitlement failures are tested without exposing tokens. Unsupported Claude/OpenCode subscription flows remain unavailable with a clear explanation.
3. **Inference adapters and discovery:** keep authentication independent from request protocol (Responses, Chat Completions, Anthropic Messages, Copilot SDK, local compatible endpoint). Acceptance: each enabled connection discovers only its models, sends lesson context, normalizes errors, and never displays models for a disconnected/expired account.
4. **Unified connection UI and docs:** show one card per provider with clearly named sign-in/API-key/local methods, usage billing disclosure, connection state, and disconnect. Acceptance: keyboard/accessibility and responsive checks pass; test/mocked flows cover each auth method; local run docs explain provider setup and limits.
5. **gpt-oss experiment (after phase 5):** connect via Ollama using the generalized local connection path and run the same fixed five-prompt accuracy rubric against Qwen3 14B. Acceptance: save full outputs, correctness/unsupported-claim scores, latency, machine/model settings; do not interpret an app timeout as model accuracy.

**Official references checked:** [Anthropic Claude authentication](https://platform.claude.com/docs/en/manage-claude/authentication), [Claude Code sign-in options](https://docs.anthropic.com/en/docs/claude-code/getting-started), [OpenCode providers](https://opencode.ai/docs/providers/), [OpenCode provider authentication](https://opencode.ai/docs/cli/providers/), and [GitHub Copilot SDK authentication](https://docs.github.com/en/copilot/how-tos/copilot-sdk/auth/authenticate).

## Completion checkpoint

- [ ] All tracker tasks and checkpoints are complete.
- [ ] Local end-to-end path is verified from clean startup through sign-up, practice, progress save, AI help (with configured credentials), and sign-in persistence.
- [ ] Existing tutorial and demo builds remain intact.
- [ ] External deployment prerequisites are listed; no live deployment is claimed without verification.
