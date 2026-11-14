# Developer Studio learning platform

## Goal

Turn the existing PostgreSQL and event-driven backend tutorials into a usable learning product. Learners should read the existing lessons, run PostgreSQL examples, get graduated help, complete checkpoints, and return later to find their course progress saved to an account.

## Audience and success criteria

- Android developers learning SQL, PostgreSQL, FastAPI, concurrency, and event-driven systems.
- The selected Developer Studio design is the visual reference: calm dark surfaces, a compact course rail, focused lesson and query workspace, and contextual coach.
- A learner can create an account, work through every core chapter, run a real PostgreSQL-compatible query, request a nudge/hint/solution, and see progress persist after signing out and back in.
- Learners can use static course-authored help without connecting an AI provider. Connecting a provider enables an interactive assistant and must clearly explain how usage is billed.
- The app runs locally from documented commands. Public deployment is a separate hosting step because GitHub Pages cannot run the account/API service.

## Existing system

- `src/*.md` is the course source; `tools/build.py` renders it to `site/*.html` for GitHub Pages.
- `project/app` is a separate FastAPI/PostgreSQL ChaiPoint API example. Keep it focused on the tutorial and do not mix learner-account tables into its order schema.
- `design/learning-playground` and `screenshots/` contain approved, static design previews. Reuse the Developer Studio language without copying the simulated interactions as if they were production behavior.

## Product behavior

1. **Course and lesson navigation:** list chapters from the repository content; show current lesson, completion state, and overall progress.
2. **SQL playground:** run SQL against a PostgreSQL-compatible PGlite database in the browser. Seed it with ChaiPoint tables and data. Persist the database in IndexedDB; provide a reset action. Learner SQL stays in the browser.
3. **Practice and help:** each core chapter has an explicit activity. A static nudge, hint, solution, and explanation are always available. An AI coach is optional and uses the current lesson and learner-selected help level as context.
4. **Accounts and progress:** email/password course accounts; save chapter completion and exercise attempts per account in the learning service's SQLite database. Use HTTP-only session cookies and a persistent configurable data directory.
5. **Provider connections:** keep course identity separate from AI usage. Support OpenAI API keys, Anthropic Console API keys, OpenCode Console API keys, and OpenAI's open-source Sign in with ChatGPT plan-use flow when the app runs on the learner's own machine. Encrypt credentials using an environment-provided key; disconnect deletes them. Show provider-specific billing copy before connecting.
6. **Provider limits:** ChatGPT plan use is separate, opt-in permission for eligible users, and its OAuth tokens must remain in local user-controlled storage; enable this flow only on the loopback app. A remote backend cannot use or store those tokens. An OpenAI API key remains available with separate API billing. Claude Pro/Max subscriptions do not include Console API usage; OpenCode API keys are billed to the user's Console budget/plan.
7. **Responsive/accessibility:** keyboard access, visible focus, labeled controls, non-color state cues, reduced-motion support, and usable layouts at 320, 768, 1024, and 1440 pixels.

## Architecture

- Add a separate `learning_app` FastAPI application. It serves the built course, playground assets, and JSON endpoints from one origin for local use.
- Keep the frontend small and use the approved vanilla HTML/CSS/JS design. Use PGlite as the PostgreSQL-compatible browser engine; bundle and pin it rather than relying on a runtime CDN.
- Use SQLite for course identity, sessions, progress, and encrypted provider credentials. Store its path in `LEARNING_DB_PATH`; credential storage requires a stable `LEARNING_CREDENTIAL_KEY`.
- Call provider APIs from the service so keys never enter browser storage. Keep ChatGPT plan-use tokens in the user's local loopback runtime only, and call that user's provider only after an explicit assistant request. On remote deployments, disable SIWC and use user-provided API keys instead.
- Keep the existing GitHub Pages output working. The static Pages host can continue serving lessons, but authenticated progress and AI require the FastAPI service. Include a local Docker setup and deployment notes; do not claim a public backend is deployed without a configured host.

## Security and failure handling

- Hash passwords and session tokens; never log credentials or prompts containing user secrets.
- Encrypt provider credentials at rest. If the encryption key is missing, disable AI connection and explain why; do not fall back to plaintext.
- Validate account input, constrain SQL result rendering, catch query/provider errors, and keep saved progress intact when AI is disconnected or unavailable.
- Do not execute learner SQL on the service database. The browser PGlite instance is isolated per learner browser.

## Definition of done

- [ ] A clean checkout can start the app using the documented command and seeded course data.
- [ ] Account registration/login/logout works; progress survives browser reload and a new session.
- [ ] SQL runs against real PostgreSQL-compatible browser execution and results/errors render accessibly.
- [ ] Every core chapter has an activity and graduated static help; completing an activity updates account progress.
- [ ] At least one configured provider completes an assistant request; local ChatGPT plan use and OpenAI, Anthropic, and OpenCode API-key paths have provider-specific validation/error handling.
- [ ] Provider secrets are encrypted and disconnectable; billing/eligibility limits are disclosed accurately.
- [ ] Responsive and keyboard flows are manually checked; automated backend and browser-flow checks pass.
- [ ] Existing lesson build and demo API remain functional; local deployment and external prerequisites are documented.

## External prerequisites

- OpenAI's open-source SIWC flow supports eligible ChatGPT Plus/Pro users in locally run open-source apps; users separately grant `chatgpt.tokens.use.direct`. SIWC tokens stay local and user controlled. Website identity-only SIWC is a separate integration.
- Anthropic Console API keys use API billing. Claude.ai Pro/Max subscription tokens are not supported as generic third-party API credentials.
- OpenCode Console API keys count against the key owner's workspace budget/plan; free models may be unavailable outside OpenCode.
- Public deployment requires a backend host with persistent storage and secrets; the current GitHub Pages workflow only deploys static files.

## References

- [OpenAI: Sign in with ChatGPT quickstart](https://developers.openai.com/siwc/quickstart)
- [OpenAI: open-source ChatGPT plan usage](https://developers.openai.com/siwc/token-sharing-open-source)
- [OpenAI: open-source sign-in and registration](https://developers.openai.com/siwc/token-sharing-open-source/sign-in)
- [OpenAI: Sign in with ChatGPT terms](https://openai.com/policies/sign-in-with-chatgpt-terms/)
- [Anthropic: Claude subscription and API billing](https://support.anthropic.com/en/articles/9876003-i-subscribe-to-a-paid-claude-ai-plan-why-do-i-have-to-pay-separately-for-api-usage-on-console)
- [Anthropic: models API](https://platform.claude.com/docs/en/api/models/list)
- [OpenCode: Console inference API](https://opencode.ai/docs/console/api/inference)
- [PGlite: getting started](https://pglite.dev/docs/)
