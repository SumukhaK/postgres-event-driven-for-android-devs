# AI assistant quality and latency research

This research examines the current Developer Studio assistant and identifies changes to validate before implementation. It does not claim a guaranteed 5–10 second reduction: the existing evaluation records end-to-end response time, but not enough component timings to attribute the delay.

## Findings

### Schema accuracy

`learning_app/assistant.py:lesson_context` currently sends the lesson title, summary, and optional activity prompt. It does not send the lesson's concrete SQL schema or relevant lesson text. As a result, the model may invent plausible columns such as `active`.

The repository also has distinct schema sources for the interactive learning app and the backend course project:

- `learning_app/static/seed.sql` defines the browser playground's ChaiPoint-like sample data, including `products.category` and `orders.created_at`.
- `project/sql/001_schema.sql` defines the backend project schema, including `orders.placed_at`, and has no `products.category` column.
- Course chapters discuss schema details that need to be matched to the environment in which an answer will be used.

Before adding schema to prompts, decide which schema the assistant is answering for in each lesson and make that schema visible to the learner. Do not inject one global schema into contexts for lessons that teach another schema.

### Latency

The corrected Qwen3 14B evaluation averaged 59.2 seconds across five prompts, with a 4.3-second first/warm-up request. The assistant already disables Ollama thinking and limits output to 500 generated tokens. Local inference is likely a major contributor, but the current timings do not split model loading, prompt processing, generation, or application overhead.

A 5–10 second gain cannot be promised from code inspection alone. First measure the stages; then change the stage shown to dominate. Make perceived responsiveness (time to first visible text) a separate metric from full answer completion time.

## Recommended work, in order

1. **Reconcile schema sources.** Record the schema each lesson and exercise teaches, and align the relevant lesson text, playground seed, and expected answer. Add a small test that asserts assistant context and exercise schema agree for representative lessons.
2. **Ground the assistant with bounded schema context.** Extend `lesson_context` to include only the exact table/column definitions needed by the current lesson/activity, sourced from that learner environment. Add prompt-context tests for columns such as `products.category` and `orders.placed_at` so one environment's schema cannot leak into another.
3. **Validate SQL suggestions without executing them.** If a reply contains SQL, parse identifiers and compare them against the current exercise schema before displaying a validation notice. Never run model-generated SQL as a validation step. Keep normal prose answers available when the parser cannot confidently inspect a snippet.
4. **Instrument before latency tuning.** Record request duration, time to first visible text, provider/model, input/output token counts when provided, and outcome. For Ollama, capture its `total_duration`, `load_duration`, `prompt_eval_duration`, and `eval_duration`. Do not log prompts, credentials, or generated answers as telemetry.
5. **Test concise output budgets by action.** Nudge and hint responses can use shorter instructions/output limits than full solutions. Compare accuracy and truncation alongside latency; the existing 500-token ceiling has already truncated at least one Qwen2.5 explanation, so reducing it globally is unsafe.
6. **Stream text to the learner where supported.** Streaming should lower time to first visible text, but does not necessarily reduce the time to a complete answer. The current ChatGPT plan adapter consumes a provider stream but buffers it before the app returns the result. Measure time-to-first-token and total duration separately for each provider.
7. **Only tune model residency or prompt caching when measurements justify it.** Ollama `keep_alive` may reduce load time while consuming scarce RAM/VRAM. Prompt caching helps only when the request has a sufficiently large repeated prefix and the provider reports cache hits; measure token counts first. Reusing an HTTP client may reduce connection setup for hosted APIs, but is unlikely to remove several seconds from local generation.

## Measurement plan

- Run the same five fixed prompts against the same model/provider and hardware; preserve answer-quality scoring and truncation notes.
- Separate cold and warmed runs. Report median and p95, not only the mean.
- Capture time to first visible text and complete-response time.
- For Ollama, retain the four server timing fields and token counts when available. For cloud routes, capture client-side request timing and provider usage metadata without storing user content.
- Compare each proposed optimization independently, then keep only changes that improve the target metric without reducing schema correctness or answer usefulness.

## Tracker breakdown

- **T22 · Reconcile lesson and playground schemas.** Document the schema expected by each lesson/activity and align the relevant source materials and tests.
- **T23 · Add schema-grounded assistant context.** Supply bounded, environment-correct table/column context; add context assertions and regression prompts.
- **T24 · Measure assistant latency by stage.** Add privacy-preserving timing/usage telemetry, including Ollama duration fields, then rerun the fixed prompt suite.
- **T25 · Improve perceived response time.** Stream incremental text where providers support it and evaluate time-to-first-visible-text separately from total response latency.
- **T26 · Tune output and model residency from evidence.** Test shorter nudge/hint budgets and optional Ollama residency only against measured latency, answer quality, truncation, and memory use.

## Primary references

- [Ollama chat API](https://docs.ollama.com/api/chat) — streaming and timing fields in chat responses.
- [OpenAI latency optimization](https://developers.openai.com/api/docs/guides/latency-optimization) — reduce generated output and optimize request design.
- [OpenAI structured outputs](https://developers.openai.com/api/docs/guides/structured-outputs) — constrain output shape; structure alone does not prove SQL identifiers are valid.
- [OpenAI prompt caching](https://developers.openai.com/api/docs/guides/prompt-caching) — cache eligibility and repeated-prefix requirements.
- [Anthropic streaming messages](https://platform.claude.com/docs/en/build-with-claude/streaming) — incremental message events.
- [Anthropic prompt caching](https://platform.claude.com/docs/en/build-with-claude/prompt-caching) — cache controls and usage.
