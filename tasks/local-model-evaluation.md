# Developer Studio local model experiment

Compare response time, PostgreSQL correctness, explanation quality, and unsupported claims through the Developer Studio assistant endpoint. Use the same five lesson tasks and settings for each model; report wall-clock time from submit to complete answer, not model-internal token time. One warm-up call per model is excluded from the five scored prompts.

## Rounds

- [ ] **R1 · Qwen2.5 7B Instruct** (`qwen2.5:7b-instruct`, already installed)
- [ ] **R2 · Gemma 3 12B** (`gemma3:12b`, remove after its measurements)
- [ ] **R3 · Qwen3 14B** (`qwen3:14b`, keep installed)
- [ ] **R4 · ChatGPT account** (complete local ChatGPT sign-in and consent, then run the same prompts)

## Fixed prompts and scoring

1. Filter active products under 5 and return name and price, highest price first.
2. Join customers to orders and return customer name with order count.
3. Increment only the Samosa stock and return the changed name and stock.
4. Explain why `EXPLAIN SELECT * FROM products WHERE category = 'Tea'` may use a sequential scan on the small course table, and whether adding an index is automatically faster.
5. Explain how a transactional outbox prevents an order from committing without a durable event record.

Score each answer 0–2 for correctness, 0–2 for useful lesson-level explanation, and 0–1 for avoiding unsupported claims (5 points total). Record full-answer latency and any timeout/error. This is a small exploratory comparison, not a statistical benchmark.

## Results

| Round | Model | Mean answer latency | Score / 25 | Unsupported claims | Notes |
| --- | --- | ---: | ---: | ---: | --- |
| R1 | — | — | — | — | — |
| R2 | — | — | — | — | — |
| R3 | — | — | — | — | — |
| R4 | — | — | — | — | — |

