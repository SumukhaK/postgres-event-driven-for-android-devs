# T31: combined browser verification

Date: 2026-11-22. Scope: exercise the real local Developer Studio app and browser with a deterministic local provider stub, covering progress persistence, streamed answers, SQL warnings, sanitized mid-stream failure, request correlation, and log privacy. **No live cloud provider requests were made.**

## Harness

- **App**: direct Uvicorn run on `127.0.0.1:8000` with a dedicated verification database (`LEARNING_DB_PATH=data/browser-verification.sqlite3`) and a generated Fernet key. INFO diagnostics enabled in the console; Uvicorn access logs disabled.
- **Provider stub**: `tools/local_provider_stub.py` serves an OpenAI-compatible `/v1` on `127.0.0.1:9207`. Four scripted models make each scenario deterministic: `stub-clear-sql` (schema-valid SQL), `stub-sql-warning` (invented `products.active` column), `stub-no-sql` (prose), and `stub-fail-midstream` (chunked SSE that drops the transport after two deltas with no terminating chunk). Guarded by `tools/tests/test_local_provider_stub.py` (4 tests: catalog, complete stream, warning reply, mid-stream drop raising `httpx.HTTPError`).
- **Browser**: real Chromium-based in-app browser driving `http://127.0.0.1:8000/playground` through the normal UI (no API shortcuts for user actions).

## Scenarios and evidence

| Acceptance criterion | Result | Evidence |
| --- | --- | --- |
| Account/progress persistence | Activity completed once; attempt saved to the account; sign-out, reload, and sign-in restored `1 / 11 activities` server-side. State also survived a full app-server restart on a later run. | UI statuses: "Activity attempt saved to your account." → "Progress synced · 1 of 11 activities complete." |
| Incremental answers before completion | Tutor text rendered progressively; the UI reports first visible text separately from total time. | "Answer ready · first text 0.5s · total 3.0s" (stub streams deltas at 350 ms pauses). Screenshot `screenshots/developer-studio-streaming-validation.png`. |
| Final SQL validation | Valid-identifier reply shows the green pass note; the invented `active` column reply shows the advisory warning without altering the answer. | "Schema check passed: table and column names match the playground." / "Schema check: review unknown table or column names (active)." |
| Sanitized mid-stream failure | The dropped chunked stream preserved both received deltas in the tutor turn, replaced completion with a sanitized error, surfaced the request ID, kept progress and controls usable. | Turn text: partial answer + "The provider could not complete this request. Try again. Reference: 603aade2…". Screenshot `screenshots/developer-studio-midstream-failure.png`. |
| Correlation and timings | The failure request ID appears in 6 server records spanning the whole lifecycle; the stream error carries `error_kind: transport`, first-body and total durations. | Log excerpts below. |
| No sensitive logging | Zero occurrences of the account email, password, three prompt texts, stub answer fragments, generated SQL, and the credential key in the server console. | `grep -c` over the full session log: 8/8 markers returned 0. |

Correlated records for the failed request (request ID `603aade268c64f1a8f87207d7afe3356`):

```
{"event":"http_request","outcome":"started",…,"route":"pending","method":"POST"}
{"event":"stage","outcome":"success",…,"stage":"lesson_context","provider":"local","model":"stub-fail-midstream","action":"ask","lesson":"00-start-here","duration_ms":1}
{"event":"assistant_stream","outcome":"started",…,"stage":"provider_inference",…}
{"event":"assistant_stream","outcome":"error",…,"error_kind":"transport","status_code":502,"duration_ms":1151,"first_body_ms":449}
{"event":"http_request","outcome":"success","route":"/api/assistant/respond/stream","status_code":200,"duration_ms":1161,"first_body_ms":459}
```

The failed stream still ends as an HTTP 200 SSE response whose final event is the sanitized `error` frame — matching the T25 contract that partial answers stay visible and failures are reported inside the stream.

## Validation

- `pytest tools/tests/test_local_provider_stub.py -q` passed 4 tests; full suite `pytest learning_app/tests tools/tests -q` passed locally before the PR.
- **PR #10 CI ([run 45002269445](https://github.com/SumukhaK/postgres-event-driven-for-android-devs/actions/runs/45002269445), 2026-11-22) passed**: 108 Python tests (incl. the 4 new stub protocol tests), both builds, sandbox/exercise suites, 59 course SQL blocks and 13 demo tests.
- Browser flow executed twice (once before an environment restart, once after), reproducing every scenario; the second run doubles as restart-persistence evidence.

## Limits

- The stub fixes answer **content**, not answer quality; it cannot model real provider behavior such as variable latency or provider-side errors. Cloud/GPT behavior remains out of scope (skipped by user request).
- One browser, one account, one lesson activity were exercised; multi-account isolation and concurrency are covered by backend tests rather than this browser run.
- Browser console diagnostics were observed through the UI timings and statuses; the console-side `studio_api_response`/`studio_assistant_timing` records ship in `app.js` and were verified in earlier tasks (T28).
