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

## Phase 6 · Tutor reliability, responsiveness, and diagnostics

Keep the application local-first. Implement these as separate, reviewable changes in `tasks/todo.md`; create one branch and PR per task, review each diff, then merge only into this repository's `main`.

### Work order and dependencies

1. **T28 · Privacy-safe diagnostics (foundation).** Add a request/correlation ID and structured, local-only events across browser request, account/progress routes, provider connection/model discovery, lesson-context assembly, assistant request, SQL validation, and response completion/failure. Include stage durations, provider/model/action/lesson identifiers where safe, outcome categories, and time to first visible text when streaming is added. Never record prompts, generated answers, account emails, keys/tokens, OAuth codes/state, or complete authorization URLs. **Acceptance:** a failed request can be reconstructed by ID and stage without content or credentials appearing in logs; errors remain sanitized to learners.
2. **T29 · Non-executing SQL identifier validation.** Select a PostgreSQL AST parser compatible with the current Python stack. Inspect only clearly delimited SQL suggestions, resolve supported table/alias/column references against the active playground schema, and return an advisory status. Treat ambiguous, unsupported, or partially generated SQL as unchecked rather than valid. **Acceptance:** catches the known nonexistent-column case and handles aliases/joins/CTEs in the supported subset; prose and answer text remain intact; generated SQL is never executed for validation.
3. **T25 · Stream answers and measure perceived latency.** Send provider deltas to the browser as they arrive for supported adapters; handle completion and sanitized mid-stream errors. Log time to first visible text separately from full duration under T28's request ID. Include SQL-validation status in the final stream event. **Acceptance:** learner sees partial text promptly, a finished response is distinguishable from a partial/error response, and normal non-streaming/provider fallback paths remain usable.
4. **T26 · Tune generation from evidence.** Compare action-specific output budgets and optional Ollama residency one change at a time. Reuse the fixed prompt set, same accuracy rubric, cold/warm conditions, and available laptop resources; include answer truncation and memory use. **Acceptance:** retain a tuning only if answer quality does not regress; record measurements and hardware limits; do not load a larger model or run concurrent local model evaluations.

### Parallel work

T28 can be implemented alongside isolated T29 parser research/prototype work. T29's API/result contract must be agreed before T25 integrates validation metadata into the stream. T26 depends on stable T28 timing and T25's first-visible-text measurement, so its device evaluation comes last. Merge each task before rebasing the next dependent PR.

### Verification and rollout

- Add focused regression tests for each behavior and run the relevant app/frontend suites plus builds before each task is marked done.
- Review each PR against its acceptance criteria, inspect logs for sensitive-content leakage, and verify the final combined learner flow locally before calling the phase complete.
- Do not enable remote telemetry, public hosting, or a larger local model as part of this phase.

## Phase 7 · Close remaining local reliability work (2026-11-17)

Live provider checks are explicitly skipped at the user's request. No cloud credentials, provider consent, paid calls, public backend deployment, or new model downloads are required.

Three isolated branches start from main at `0c630de` and can progress in parallel:

1. **T30 · Tutor guidance accuracy** (`codex/tutor-guidance-quality`). Fix the source of the misleading EXPLAIN guidance and overly explicit nudges, using existing exercise references while protecting hint/solution boundaries. Expand repeatable hint/nudge cases across lessons. Acceptance: focused regression tests cover table size/selectivity and no worked-answer reference in hint/nudge context; document fixture and quality limits without inventing model scores. Files: assistant context, provider tests, evaluation fixtures/report. A bounded 7B-only live local check may follow once resource headroom is verified; no simultaneous inference or app closures without need.
2. **T31 · Combined browser verification** (`codex/studio-browser-verification`). Exercise a real local app and browser with a deterministic local provider stub: account/progress persistence, incremental answers, final SQL warning, sanitized mid-stream failure, correlation/timings, and no sensitive logging. Acceptance: evidence of partial output before completion, progress retained across login/reload, warnings and failure recovery visible, logs free of synthetic secrets/prompt markers. Own browser test harness and report; coordinate production fixes with T30 if needed. No live cloud requests.
3. **T32 · CI and Pages verification** (`codex/studio-ci-pages`). Add least-privilege CI for Python app tests, JS sandbox/exercise tests, frontend/course builds, and PostgreSQL demo tests against an isolated PostgreSQL service with a `_test` database. Verify the real Pages configuration and live course URL before updating README wording. Acceptance: all jobs pass on GitHub; no destructive test target can be a real database; Pages remains static only. Own workflows, CI docs and README Pages wording.

Parent owns tracker/upkeep integration and PR reviews. Branches do not edit the shared tracker in parallel. Each implementation branch gets a focused commit, push, PR, separate review, and merge only after its relevant checks pass. After merges, verify the combined tree and update completion checkpoints with explicit remaining limits. Existing unfinished work and historical reports are preserved.
