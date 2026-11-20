# T30: tutor guidance fixture and limits

Dates: 2026-11-20. Scope: correct the two repeatable guidance failures recorded in T26 and broaden hint/nudge coverage. **No model scores were produced in this change**; scoring quality limits are documented here so a future bounded local check starts from a fixed fixture.

## T26 findings addressed

1. **Misleading EXPLAIN explanation.** Qwen3 14B explained that index lookups are fast and full-table scans are slow, which is wrong for the tiny seed table: PostgreSQL weighs table size and selectivity, and an index is not automatically faster. Root cause: the verified explanation reference reached the tutor only for `ask` and `solution`, so the `explanation` action answered from generic priors.
2. **Overly prescriptive nudge.** Qwen2.5 7B's nudge supplied the active condition, sorting, and projection explicitly, leaving little for the learner to decide.

## Changes

- `learning_app/assistant.py` (`lesson_context`): the `explanation` action now carries a verified explanation reference (the explanation text only, never the worked query). Hint and nudge contexts remain free of both solution and explanation references.
- `learning_app/assistant.py` (system instructions and nudge action prompt): nudges must point at the kind of step to consider without naming exact columns, values, or clauses; hints may name specific identifiers but must leave the query to the learner.
- `learning_app/tests/test_tutor_guidance.py`: 35 regression checks parametrized across all 11 exercises — no answer references in hint/nudge context, grounded-but-not-worked explanation context, intact ask/solution references, the EXPLAIN table-size/selectivity case, and the nudge gentleness wording.

The explanation boundary is consistent with the static help system: the Explain button already shows each exercise's explanation text to any learner, so grounding the `explanation` action with the same text leaks nothing the product does not already show. Hints and nudges stay grounded in schema identifiers only.

## Repeatable fixture

[evaluations/hint-nudge-cases.json](evaluations/hint-nudge-cases.json) fixes nine cases across seven lessons — three nudge/hint pairs, an EXPLAIN explanation (the T26 failure mode), an outbox hint, and an update nudge — each with a quality boundary (what a good answer does) and a leakage boundary (what the answer must not add). Future checks must reuse these prompts verbatim, along with the app's context builder, so results stay comparable.

## Quality limits and what this change does not establish

- The regression tests cover **context assembly only**. They prove the tutor receives or withholds references as designed; they do not measure whether any model follows the boundaries.
- The fixture is small (nine cases) and authored by the same assistant that wrote the fix, so it is not an independent benchmark.
- A future bounded 7B-only local check may score these cases, but only after resource headroom is verified, one model at a time, with no concurrent inference or app closures (T26 trial policy). Any scores must come from that run; none are recorded here.
- Cloud/GPT behavior and browser paint timing remain outside these local checks, as in T26.
