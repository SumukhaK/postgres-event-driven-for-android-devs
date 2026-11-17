# T26: output limits and model residency

Dates: 2026-11-16 (7B) and 2026-11-17 (14B). **Decision: retain the current production settings.** Both models completed 24 requests. A shorter hint/nudge ceiling did not produce a repeatable speed improvement. Warm model reuse helped, but the app already permits it through Ollama's default residency policy. No production token limit, prompt, or residency setting changed.

## Method

Both trials used the app context builder from `8e84b9a` and Ollama 0.40.16 with installed Q4_K_M models. Hardware: GTX 1650 Ti, 4 GiB VRAM, approximately 16 GB RAM. During the 7B run, ZCode and Codex remained open; ZCode was temporarily closed for 14B. No model download was performed.

`tools/evaluate_t26.py` sends native Ollama requests using the app's exact instructions and exercise context. This measures provider behavior with app context; it does **not** exercise login, browser rendering, or the HTTP assistant route. First text means client receipt, not first visible browser paint. Public exercise prompts and answers are deliberately saved in [the raw results](evaluations/t26-qwen2.5-7b-instruct.json); no account data or credentials are used.

- Sampling: seed 42, temperature 0, context 4096, thinking disabled, explicit `keep_alive: "5m"`.
- Residency: two pairs using the same index explanation prompt. Unload before each cold request; immediately repeat while resident for the warm request.
- Budgets: five fixed cases cover nudge (SELECT), hint (JOIN), solution (UPDATE), explanation (EXPLAIN), and ask (outbox). Each case runs control then candidate in repeat 1, candidate then control in repeat 2. Control is 500 tokens; candidate is 160 only for nudge/hint. Other actions remain at 500 and serve as unchanged controls.
- This mixed-action fixture differs from the earlier five-question evaluation. Its quality scores must not be compared with the earlier 25/25 results.
- All 24 requests completed, none reported truncation (`done_reason: stop`), and the model was unloaded afterward. No changes to other applications were made during the 7B measurement sequence.

## 7B output-budget result

| Measurement | Control | Short-help candidate |
| --- | ---: | ---: |
| Budget requests completed | 10/10 | 10/10 |
| Mean total response | 8.831 s | 8.762 s |
| Median total response | 6.525 s | 6.207 s |
| Nearest-rank p95 | 14.945 s | 14.848 s |
| Mean first-text receipt | 0.878 s | 0.688 s |
| Mean prompt processing | 0.857 s | 0.666 s |
| Mean generation | 7.954 s | 8.074 s |

These aggregate rows include unchanged controls. The tiny 0.069-second mean difference is not evidence for changing the cap. With only 10 observations per variant, p95 is simply the largest observation.

| Changed action | Tokens, either limit | Repeat 1: control / candidate | Repeat 2: candidate / control |
| --- | ---: | --- | --- |
| Nudge | 37 | 6.294 / 5.438 s | 6.655 / 5.717 s |
| Hint | 25 | 4.615 / 3.743 s | 4.620 / 3.619 s |

The cap never bound either answer. All four nudge texts were identical, as were all four hints. The second request was faster in both orders. Native timings show prompt processing falling from roughly 1.6–1.7 seconds to 0.14–0.17 seconds on the second request; this is consistent with prefix reuse, not shorter generation. **Reject the 160-token setting:** there is no demonstrated benefit, and this small fixture cannot establish that it would avoid truncating other hints.

## 7B residency result

| Same explanation prompt | Cold mean | Warm mean |
| --- | ---: | ---: |
| Total response | 27.021 s | 13.218 s |
| First-text receipt | 14.368 s | 0.172 s |
| Model loading | 10.938 s | 0.007 s |
| Prompt processing | 3.407 s | 0.155 s |
| Generation | 12.656 s | 13.047 s |

The two cold/warm pairs were 27.883/13.167 seconds and 26.159/13.269 seconds. Reuse saved 13.803 seconds on average, including both model loading and prompt-cache effects. The four explanation answers were identical. This compares unloaded versus immediately reused requests; it does not test five-minute expiry or prove that a longer residency is useful.

Ollama reported approximately 4.80 GiB of resident model allocation, including 2.15 GiB on the GPU. This allocation is not identical to process working-set memory. Sampled free system RAM reached a minimum of 1.96 GiB during the trial and returned to 5.36 GiB after unloading; `/api/ps` then reported no resident models. System RAM reflects other applications too, and the 0.5-second sampler can miss brief peaks.

**Retain the server residency default.** Avoid unloading between every learner question, but do not pin this model indefinitely on the laptop. The app currently omits `keep_alive`, so the server configuration controls residency. This server reported `5m`; Ollama also documents five minutes as the default. See the [Ollama FAQ](https://docs.ollama.com/faq#how-do-i-keep-a-model-loaded-in-memory-or-make-it-unload-immediately) and [timing fields](https://docs.ollama.com/api/chat).

## 7B manual answer review

All distinct responses were reviewed against the playground schema and exercise references. The existing rubric is correctness (0–2), usefulness (0–2), and avoiding unsupported claims (0–1). Review was unblinded and performed by the coding assistant, not an independent evaluator.

| Action | Correctness / usefulness / supported | Findings, both variants |
| --- | --- | --- |
| Nudge | 2 / 1 / 1 | Correct identifiers, but supplies the active condition, sorting, and projection explicitly. It omits the price filter and does not reveal a complete answer; still too prescriptive for a gentle nudge. |
| Hint | 2 / 2 / 1 | Suggests INNER JOIN and the linking customer id without giving the full query. |
| Solution | 2 / 2 / 1 | Correct stock increment, Samosa WHERE clause, and RETURNING. Prose differs slightly; SQL is identical. |
| Explanation | 2 / 1 / 1 | Correct general purpose of EXPLAIN; shallow on table size/selectivity and why the tiny table may use a sequential scan. |
| Ask | 2 / 2 / 1 | Correct: order and event commit together; worker retries publication without repeating the order write. |

Each five-case set scores 23/25 under this rubric, for both variants and both repeats. This supports no quality difference in these cases, not general reliability. SQL was reviewed without executing it. The current automated validator reports the generated UPDATE with RETURNING as `unchecked`; it must not be described as an automatically validated query.

## 14B trial

The first 14B attempts stopped before inference because only about 6–7 GiB was free. After authorized app cleanup, including temporarily closing ZCode and closing Firefox normally, Windows reported about 8.30 GiB free and the unchanged 8 GiB preflight passed. This threshold is an experiment safety policy for the 4 GiB GPU laptop, not a universal 14B requirement. The installed Qwen3 14B Q4_K_M model completed all 24 requests with `done_reason: stop`; none were truncated. [Raw 14B results](evaluations/t26-qwen3-14b.json) include source hashes, native timings, and every answer. The context source was unchanged from the 7B trial.

### Output budget

| Measurement | Control | Short-help candidate |
| --- | ---: | ---: |
| Budget requests completed | 10/10 | 10/10 |
| Mean total response | 19.336 s | 19.288 s |
| Median total response | 16.930 s | 16.793 s |
| Nearest-rank p95 | 36.725 s | 35.850 s |
| Mean first-text receipt | 2.350 s | 2.338 s |
| Mean prompt processing | 2.307 s | 2.309 s |
| Mean generation | 16.986 s | 16.950 s |

| Changed action | Tokens across both limits | Repeat 1: control / candidate | Repeat 2: candidate / control |
| --- | ---: | --- | --- |
| Nudge | 25–27 | 12.426 / 9.882 s | 12.337 / 9.689 s |
| Hint | 29–30 | 14.955 / 10.472 s | 14.083 / 10.490 s |

Again, the second request was faster regardless of the cap. Each action's two prose variants occurred under both limits, following request order. Neither ceiling bound generation. The aggregate mean difference was only 0.048 seconds and includes three unchanged action controls. **Reject the shorter cap for 14B too.**

### Residency and memory

| Same explanation prompt | Cold mean | Warm mean |
| --- | ---: | ---: |
| Total response | 46.753 s | 19.924 s |
| First-text receipt | 27.793 s | 0.415 s |
| Model loading | 20.032 s | 0.012 s |
| Prompt processing | 7.736 s | 0.395 s |
| Generation | 18.963 s | 19.509 s |

The pairs were 48.332/19.820 seconds and 45.173/20.028 seconds: immediate reuse saved 26.829 seconds on average, combining loading and prompt-cache effects. The four answers were identical, including the accuracy issue below. This does not establish that a longer idle residency is worthwhile.

Ollama reported 9.47 GiB resident allocation, including 2.06 GiB on the GPU. Sampled free system RAM fell to 1.51 GiB and returned to 10.01 GiB after unloading; `/api/ps` was empty. As with 7B, allocation is not process RSS and RAM includes other apps. The sampler checks every 0.5 seconds; abort checks happen when stream lines arrive, so these guards are not a hard allocation limit. ZCode, OneDrive, and Google Drive were restored after unloading; the local proxy was checked healthy.

### Manual answer review

Every distinct 14B answer was reviewed using the same unblinded rubric as 7B.

| Action | Correctness / usefulness / supported | Findings, both variants |
| --- | --- | --- |
| Nudge | 2 / 2 / 1 | Points toward filtering and ordering without giving the answer. |
| Hint | 2 / 2 / 1 | COUNT, JOIN, and grouping are appropriate for counting each customer's orders; no complete query revealed. |
| Solution | 2 / 2 / 1 | Correct scoped stock increment and RETURNING; same SQL in every response. |
| Explanation | 1 / 1 / 0 | Describes index lookup as fast and a full-table scan as slow. This is misleading for the tiny seed table: indexes are not automatically faster. |
| Ask | 2 / 2 / 1 | Correct atomic order/event commit and retry of event delivery. |

Each five-case set scores **22/25**, unchanged between limits and repeats. No invented table/column names were found. The UPDATE was manually checked, not executed or certified by the automated validator. The EXPLAIN error needs a separate grounding/accuracy improvement; output limits did not fix it. The new fixture is not comparable to the earlier five-question scores.

## Decision and limits

Keep the 500-token ceiling and server-controlled residency. No production change is justified by this trial. Follow up with broader hint/nudge cases and correct the index explanation guidance before claiming reliable tutoring across these actions.

The two models ran on different days with different background applications; compare each model's control/candidate pairs rather than interpreting their absolute times as a controlled model ranking. Cloud/GPT behavior and browser paint latency are outside this local residency trial.
