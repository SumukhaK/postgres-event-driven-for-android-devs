# Developer Studio AI evaluation

Five fixed PostgreSQL prompts were sent through the Developer Studio assistant endpoint. Each model received one warm-up request, excluded from mean latency. Scores are exploratory: correctness (0–2), lesson-level explanation (0–2), and avoiding unsupported claims (0–1), for 25 total. A timeout is an application failure and is not scored as a model answer.

## What changed after the first run

The initial local-model run used a 45-second request timeout and reported several timeouts as if they were usable model results. That was invalid. The app now allows up to 180 seconds for a local response, identifies Ollama endpoints, and routes Ollama chat through its native API with Qwen3 thinking disabled. The general OpenAI-compatible route remains in use for other local servers. The UI also tells learners their progress is safe and offers retry/static help after an AI request fails.

Qwen3's initial timeouts were caused by the Ollama route not disabling its default thinking mode, as well as the app's short timeout. Qwen3 14B then completed all five prompts with the fixed route. Those first-run timeouts are retained only as a record of the product bug, not as model scores.

## Corrected runs

| Model | Warm-up | Mean scored latency | Answers completed | Score | Notes |
| --- | ---: | ---: | ---: | ---: | --- |
| Qwen2.5 7B Instruct (`qwen2.5:7b-instruct`) | 2.6 s | 37.1 s | 5/5 | 10/25 | Incorrect/invented schema in prompts 1–3; prompt 4 was useful but truncated; outbox answer misdescribed the transaction boundary. |
| Qwen3 14B (`qwen3:14b`) | 4.3 s | 59.2 s | 5/5 | 16/25 | Better explanations on prompts 4–5; schema mismatches in prompts 1–3. Model remains installed. |
| ChatGPT plan (`gpt-6.1-sol`) | 5.6 s | 9.2 s | 5/5 | 22/25 | One incorrect `active` column; the other four answers matched the course schema and concepts. Connected locally using the user's ChatGPT plan after consent. |

### Corrected run latency by prompt

| Prompt | Qwen2.5 7B | Qwen3 14B | ChatGPT plan |
| --- | ---: | ---: | ---: |
| Filter/sort active products | 23.524 s | 33.059 s | 5.670 s |
| Join customers and count orders | 30.716 s | 67.330 s | 7.705 s |
| Increment Samosa stock | 15.360 s | 42.923 s | 8.489 s |
| Explain sequential scan/index choice | 68.753 s | 88.571 s | 11.941 s |
| Explain transactional outbox | 47.254 s | 64.304 s | 12.006 s |

Scores are based on review against the course schema in `learning_app/static/seed.sql` and lesson material. The 7B score by prompt was 2, 1, 2, 4, 1; Qwen3 14B was 2, 2, 2, 5, 5; ChatGPT was 2, 5, 5, 5, 5. The 7B index explanation was cut off by the 500-token answer cap, which limited its usefulness.

## Recommendation

Prioritize answer accuracy over latency. Of the local models actually retested, Qwen3 14B is the stronger candidate (16/25 versus 10/25 for Qwen2.5 7B), though both made repeated schema mistakes and neither should be treated as a reliable SQL authority yet. Validate the 14B model on better hardware before choosing a local default; its 59-second result on this laptop reflects the current hardware and is not a reason by itself to prefer the less accurate 7B model. The ChatGPT plan scored highest in this small sample (22/25). Include course schema context in every AI prompt and keep generated SQL reviewable. The 4 GB GPU and 16 GB RAM limit local inference speed and model headroom, not the accuracy-first selection criterion.

This is a five-prompt, one-session comparison, not a statistically controlled benchmark. Latency varies with model load, machine state, and provider service conditions. No timeout from the pre-fix run is used to claim lower model accuracy.

## Schema/reference context optimization trial

The trial adds the playground seed schema for only the current exercise's relevant tables, a verified exercise answer/explanation for `ask` and `solution` requests, and concise tutor instructions. Hint requests do not receive the answer reference. Ollama INFO logs now record request/load/prompt/generation durations and token counts without logging prompts, answers, or credentials. The baseline code is preserved at `codex/pre-optimization-baseline`.

| Model | Warm-up | Mean scored latency | Per-prompt latency | Completed | Score |
| --- | ---: | ---: | --- | ---: | ---: |
| Qwen2.5 7B Instruct (`qwen2.5:7b-instruct`) | 16.51 s | 9.64 s | 8.42, 14.17, 5.98, 10.58, 9.04 s | 5/5 | 25/25 |
| Qwen3 14B (`qwen3:14b`) | 26.23 s | 29.17 s | 26.55, 32.32, 31.14, 25.73, 30.12 s | 5/5 | 25/25 |
| ChatGPT plan (`gpt-6.1-sol`) | 3.45 s | 4.50 s | 4.41, 4.26, 4.22, 4.85, 4.74 s | 5/5 | 25/25 |

The five latency positions follow the prompt order in the prior table. All three providers' five responses were manually reviewed against `learning_app/static/seed.sql` and the verified exercise references and scored 5/5 per prompt. Compared with the earlier runs, the 7B mean fell from 37.1 s to 9.64 s (+15 points), the 14B mean fell from 59.2 s to 29.17 s (+9 points), and ChatGPT fell from 9.2 s to 4.50 s (+3 points). The GPT warm-up took 3.45 s and was excluded from the mean. These observations do not isolate the code change: the new prompt includes verified answers for these exercise requests, the earlier literal prompt text was not retained and was reconstructed from exercise descriptions, and machine/network conditions differed. Treat this as a promising end-to-end assistant trial, not evidence that the base models alone improved.

The first fresh GPT sign-in attempt reached the local callback but failed during token exchange because the evaluation server could not make outbound connections from its restricted process. Restarting the isolated server with outbound access allowed the token exchange and the completed run above; the failed attempt was not scored.

The optimization code and results are on `main` per the user's direction. If later evaluations do not reproduce a useful improvement, restore the pre-optimization version from `codex/pre-optimization-baseline` and rerun the suite.

## T26 output/residency tuning · completed 2026-11-17

The follow-up completed 24 requests each for Qwen2.5 7B and Qwen3 14B, covering nudge, hint, solution, explanation, and ask. It compared 500-token controls with a 160-token ceiling for hints/nudges, plus two cold/warm residency pairs per model. All 48 requests completed without truncation and both models were unloaded after measurement.

**Decision: retain existing settings.** The lower cap did not bind or show a repeatable speed benefit. Immediate model reuse saved 13.803 seconds for 7B and 26.829 seconds for 14B on average, combining loading and prompt-cache effects. The app already leaves residency to the server; a longer idle timeout was not tested or adopted.

The new action fixture is different from the earlier five-question evaluation, so its manual scores (7B 23/25, 14B 22/25, unchanged between settings) are not a before/after comparison. 14B misleadingly described sequential scans as slow; this remains an accuracy follow-up. These native API trials measured first-text receipt, not browser paint or login. See the [complete report, stage timings, memory readings, raw answers, and limitations](t26-tuning-results.md).

The current API and residency behavior are described in the [Ollama chat API](https://docs.ollama.com/api/chat) and [Ollama local FAQ](https://docs.ollama.com/faq#how-do-i-keep-a-model-loaded-in-memory-or-make-it-unload-immediately).
