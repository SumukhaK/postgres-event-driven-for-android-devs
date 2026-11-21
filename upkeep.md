# Developer Studio upkeep

This is a follow-up list, not a release blocker. The current goal remains a locally run learning playground; public hosting is optional and is not planned by default. Revisit items when there is a concrete need, and keep the AI accuracy checks in place while making changes.

## Provider verification

**Skipped for the current work by user request (2026-11-17).** The unchecked live-provider items below remain optional future work, not part of the current completion gate.

- [ ] Run one live, consented end-to-end check with an Anthropic Console key and one with an OpenCode Console key: connect, discover models, ask about a lesson, receive an answer, disconnect. Current coverage uses mocked provider responses; the documented live evaluation used ChatGPT plan access and local Ollama models.
- [ ] If OpenAI API-key support will be offered separately from ChatGPT plan access, run the same live flow with an OpenAI API key and confirm its billing disclosure is clear.

Use test accounts/keys with a known spend limit. Never add credentials or learner prompts to logs or this repository.

## Tutor accuracy and safety

- [ ] Broaden the repeatable hint/nudge evaluation beyond T26's one case each. 7B's nudge was too prescriptive; 14B's hints were appropriate in this small fixture. Neither establishes general hint accuracy. The fixed nine-case fixture now exists ([evaluations/hint-nudge-cases.json](tasks/evaluations/hint-nudge-cases.json)); actual model scoring still awaits a bounded live local check with verified resource headroom.
- [x] Ground EXPLAIN explanations in the exercise's table-size/selectivity guidance without exposing solutions to hints. T26's 14B answers incorrectly implied full-table scans are inherently slow under both output limits; add regression cases before accepting a fix. Done in PR #9: the `explanation` action now carries the verified explanation reference, hints/nudges stay reference-free (regression-tested across all exercises), and the EXPLAIN grounding case is covered in `learning_app/tests/test_tutor_guidance.py`. Context assembly is verified; whether models follow the boundaries still needs the bounded live check above.
- [x] Add advisory SQL identifier checks without executing generated SQL (PR #3). Unsupported/ambiguous statements remain unchecked; this does not prove query correctness.
- [ ] Keep the schema/reference-context behavior only while repeated checks show it helps without leaking worked answers into hint/nudge responses. The current 5-prompt comparison is exploratory, not a controlled model-only benchmark.

## Responsiveness and local inference

- [x] Stream partial answers and expose first-visible/total timing (PR #4). A combined live browser check remains in the task tracker.
- [x] Compare a 160-token hint/nudge ceiling against 500, with explanation/solution/ask unchanged controls. T26 completed 24 requests per local model with no truncation; the lower ceiling did not bind or help. Retain 500. See [results and quality review](tasks/t26-tuning-results.md).
- [x] Measure unloaded versus immediate resident reuse: mean savings of 13.803 s (7B) and 26.829 s (14B), including prompt-cache effects. Keep server-controlled residency; longer idle timeouts were not tested and may occupy scarce RAM unnecessarily.
- [ ] For future comparisons, use the same prompts, model, hardware, and warm-up policy; report per-prompt results and median/p95 as well as the mean. Preserve the distinction between inference failures and answer-quality scores.

## Build and operations

- [ ] Add automated CI for the app checks and the separate PostgreSQL demo tests. The demo tests require `psycopg` and a disposable test database whose name ends in `_test`; keep their destructive fixture isolated from any real database.
- [ ] Before claiming the static course is deployed, confirm the GitHub Pages source and live URL. The repository has a Pages workflow, but the root README still describes that URL as conditional.
- [ ] If public full-stack hosting becomes a goal, plan it separately: use HTTPS, persistent storage, backups, secret management, and an abuse/rate-limit strategy. GitHub Pages only serves the static course; it is not the account/AI backend.

## Explicitly out of scope for now

- No public backend deployment is required for the current local-learning goal. Keep the interactive app local and the Pages site static unless that goal changes.
- Do not resume the `gpt-oss` evaluation or download larger local models without a new request. The tracker records the previous run as stopped for the laptop's hardware limits.
