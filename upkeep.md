# Developer Studio upkeep

This is a follow-up list, not a release blocker. The current goal remains a locally run learning playground; public hosting is optional and is not planned by default. Revisit items when there is a concrete need, and keep the AI accuracy checks in place while making changes.

## Provider verification

- [ ] Run one live, consented end-to-end check with an Anthropic Console key and one with an OpenCode Console key: connect, discover models, ask about a lesson, receive an answer, disconnect. Current coverage uses mocked provider responses; the documented live evaluation used ChatGPT plan access and local Ollama models.
- [ ] If OpenAI API-key support will be offered separately from ChatGPT plan access, run the same live flow with an OpenAI API key and confirm its billing disclosure is clear.

Use test accounts/keys with a known spend limit. Never add credentials or learner prompts to logs or this repository.

## Tutor accuracy and safety

- [ ] Add a small, repeatable hint/nudge evaluation. Existing model scores cover five SQL and explanation prompts; they do not establish hint accuracy.
- [ ] Consider a non-executing SQL check that compares generated table and column names with the active playground schema. Show a validation warning when identifiers do not match; never execute generated SQL as validation. Schema grounding is helpful but does not prove every query is valid.
- [ ] Keep the schema/reference-context behavior only while repeated checks show it helps without leaking worked answers into hint/nudge responses. The current 5-prompt comparison is exploratory, not a controlled model-only benchmark.

## Responsiveness and local inference

- [ ] Stream partial answers where supported and measure time to first visible text separately from total answer time. The ChatGPT route currently consumes its provider stream but buffers it before responding to the browser.
- [ ] Compare action-specific output limits for nudges, hints, explanations, and solutions. Track answer quality and truncation; the current 500-token cap already truncated one evaluated answer, so do not lower it globally without evidence.
- [ ] Test Ollama model residency (`keep_alive`) only when useful on the target machine. Record cold/warm latency and memory use; residency can reduce model reload time while consuming RAM/VRAM.
- [ ] For future comparisons, use the same prompts, model, hardware, and warm-up policy; report per-prompt results and median/p95 as well as the mean. Preserve the distinction between inference failures and answer-quality scores.

## Build and operations

- [ ] Add automated CI for the app checks and the separate PostgreSQL demo tests. The demo tests require `psycopg` and a disposable test database whose name ends in `_test`; keep their destructive fixture isolated from any real database.
- [ ] Before claiming the static course is deployed, confirm the GitHub Pages source and live URL. The repository has a Pages workflow, but the root README still describes that URL as conditional.
- [ ] If public full-stack hosting becomes a goal, plan it separately: use HTTPS, persistent storage, backups, secret management, and an abuse/rate-limit strategy. GitHub Pages only serves the static course; it is not the account/AI backend.

## Explicitly out of scope for now

- No public backend deployment is required for the current local-learning goal. Keep the interactive app local and the Pages site static unless that goal changes.
- Do not resume the `gpt-oss` evaluation or download larger local models without a new request. The tracker records the previous run as stopped for the laptop's hardware limits.
