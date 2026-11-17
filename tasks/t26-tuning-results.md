# T26: output limits and model residency

Date: 2026-11-16. **Decision: retain the current production settings.** A shorter hint/nudge ceiling did not shorten the answers or produce a repeatable speed improvement. Warm model reuse helped, but the app already permits it through Ollama's default residency policy. No production token limit, prompt, or residency setting changed.

## Method

The trial used the app context builder from `8e84b9a`, Ollama 0.40.16, and the installed Qwen2.5 7B Instruct Q4_K_M model. Hardware: GTX 1650 Ti, 4 GiB VRAM, approximately 16 GB RAM. ZCode and Codex remained open. No model download was performed.

`tools/evaluate_t26.py` sends native Ollama requests using the app's exact instructions and exercise context. This measures provider behavior with app context; it does **not** exercise login, browser rendering, or the HTTP assistant route. First text means client receipt, not first visible browser paint. Public exercise prompts and answers are deliberately saved in [the raw results](evaluations/t26-qwen2.5-7b-instruct.json); no account data or credentials are used.

- Sampling: seed 42, temperature 0, context 4096, thinking disabled, explicit `keep_alive: "5m"`.
- Residency: two pairs using the same index explanation prompt. Unload before each cold request; immediately repeat while resident for the warm request.
- Budgets: five fixed cases cover nudge (SELECT), hint (JOIN), solution (UPDATE), explanation (EXPLAIN), and ask (outbox). Each case runs control then candidate in repeat 1, candidate then control in repeat 2. Control is 500 tokens; candidate is 160 only for nudge/hint. Other actions remain at 500 and serve as unchanged controls.
- This mixed-action fixture differs from the earlier five-question evaluation. Its quality scores must not be compared with the earlier 25/25 results.
- All 24 requests completed, none reported truncation (`done_reason: stop`), and the model was unloaded afterward. No changes to other applications were made during the 7B measurement sequence.

## Output-budget result

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

## Residency result

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

## Manual answer review

All distinct responses were reviewed against the playground schema and exercise references. The existing rubric is correctness (0–2), usefulness (0–2), and avoiding unsupported claims (0–1). Review was unblinded and performed by the coding assistant, not an independent evaluator.

| Action | Correctness / usefulness / supported | Findings, both variants |
| --- | --- | --- |
| Nudge | 2 / 1 / 1 | Correct identifiers, but supplies the active condition, sorting, and projection explicitly. It omits the price filter and does not reveal a complete answer; still too prescriptive for a gentle nudge. |
| Hint | 2 / 2 / 1 | Suggests INNER JOIN and the linking customer id without giving the full query. |
| Solution | 2 / 2 / 1 | Correct stock increment, Samosa WHERE clause, and RETURNING. Prose differs slightly; SQL is identical. |
| Explanation | 2 / 1 / 1 | Correct general purpose of EXPLAIN; shallow on table size/selectivity and why the tiny table may use a sequential scan. |
| Ask | 2 / 2 / 1 | Correct: order and event commit together; worker retries publication without repeating the order write. |

Each five-case set scores 23/25 under this rubric, for both variants and both repeats. This supports no quality difference in these cases, not general reliability. SQL was reviewed without executing it. The current automated validator reports the generated UPDATE with RETURNING as `unchecked`; it must not be described as an automatically validated query.

## 14B trial status

The first 14B attempts stopped before inference because only about 6–7 GiB was free. The user subsequently authorized temporarily closing ZCode as well as other optional applications. On 2026-11-17, after closing Firefox normally, Windows reported 8,697,836 KiB (about 8.30 GiB) free and the unchanged 8 GiB preflight passed. This threshold is an experiment safety policy for the 4 GiB GPU laptop, not a universal 14B requirement. The 14B trial is now running; its final results and answer review are pending. The active Codex session and Windows security services remain running.

The two models ran on different days with different background applications; compare each model's control/candidate pairs rather than interpreting their absolute times as a controlled model ranking. Cloud/GPT behavior and browser paint latency are outside this local residency trial.
