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

**Priority:** make the supported GPT, Claude, and OpenCode connections clear and reliable in the local playground.

The product should present one provider-connection experience while keeping each provider's supported auth and inference behavior explicit. “Sign in with provider” means authorize model usage where a provider officially supports it; it does not mean use OAuth identity tokens as an undocumented inference credential. Keep API-key and local endpoint connections alongside account sign-in, show who bills usage, and report entitlement or unsupported-flow conditions clearly.

Provider feasibility from current official documentation:

- **OpenAI / ChatGPT:** retain the existing ChatGPT plan OAuth integration and OpenAI API-key option.
- **Anthropic / Claude:** use Anthropic Console API keys. Claude.ai subscriptions do not include Console API usage; requests are billed from Console credits or API billing. Do not reuse Claude Code credentials as third-party app credentials.
- **OpenCode:** use OpenCode Console API keys for pay-as-you-go or Go usage. OpenCode CLI provider OAuth is specific to the CLI and does not provide this app a general OpenCode Console inference token.
- **Other cloud services:** add providers through the same catalog only when official API-key, OAuth/device, or cloud identity integration details and usage/billing terms are defined. Local Ollama/vLLM/OpenAI-compatible endpoints remain a separate connection type.

### Implementation order and acceptance checks

1. **Connection contract and provider catalog:** describe provider ID, display name, supported auth methods, inference protocol, model discovery, billing source, and entitlement notes as data. Preserve current clients or migrate them compatibly. Acceptance: the UI can render supported methods from the catalog; auth mode is persisted with the encrypted connection; old connections remain usable.
2. **Supported sign-in and API-key methods:** retain ChatGPT plan sign-in and the OpenAI, Claude Console, and OpenCode Console API-key connections. Do not add unsupported consumer-plan OAuth or CLI credential reuse.
3. **Inference adapters and discovery:** keep authentication independent from request protocol (Responses, Chat Completions, Anthropic Messages, local compatible endpoint). Acceptance: each enabled connection discovers only its models, sends lesson context, normalizes errors, and never displays models for a disconnected/expired account.
4. **Unified connection UI and docs:** show one card per provider with clearly named sign-in/API-key/local methods, usage billing disclosure, connection state, and disconnect. Acceptance: keyboard/accessibility and responsive checks pass; test/mocked flows cover each auth method; local run docs explain provider setup and limits.
**Official references checked:** [Anthropic API authentication](https://platform.claude.com/docs/en/manage-claude/authentication), [Claude subscription/API billing](https://support.anthropic.com/en/articles/9876003-i-subscribe-to-a-paid-claude-ai-plan-why-do-i-have-to-pay-separately-for-api-usage-on-console), [OpenCode Console API](https://opencode.ai/docs/console/api), and [OpenCode Console models and billing](https://opencode.ai/docs/console/models).

## Completion checkpoint

- [ ] All tracker tasks and checkpoints are complete.
- [ ] Local end-to-end path is verified from clean startup through sign-up, practice, progress save, AI help (with configured credentials), and sign-in persistence.
- [ ] Existing tutorial and demo builds remain intact.
- [ ] External deployment prerequisites are listed; no live deployment is claimed without verification.
