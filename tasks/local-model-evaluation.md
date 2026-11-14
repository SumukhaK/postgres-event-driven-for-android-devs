# Developer Studio local model experiment

Compare response time, PostgreSQL correctness, explanation quality, and unsupported claims through the Developer Studio assistant endpoint. Use the same five lesson tasks and settings for each model; report wall-clock time from submit to complete answer, not model-internal token time. One warm-up call per model is excluded from the five scored prompts.

## Rounds

- [x] **R1 · Qwen2.5 7B Instruct** (`qwen2.5:7b-instruct`, already installed) — completed through the Developer Studio assistant endpoint. Warm-up: 45.3 s and timed out. Five scored answers averaged 37.9 s; three timed out. The two completed SQL answers invented table/column names and were not runnable. Preliminary score: 2/25 (both got one explanation point; zero correctness and no-unsupported-claims points).
- [x] **R2 · Gemma 3 12B** (`gemma3:12b`, removed after measurement) — warm-up timed out at 45.3 s; all five scored prompts timed out between 45.4 and 45.7 s. No answer content was available to score (0/25). The playground assistant’s 45 s provider timeout made this model unusable on this laptop in this run.
- [x] **R3 · Qwen3 14B** (`qwen3:14b`, kept installed) — warm-up timed out at 45.3 s; all five scored prompts timed out between 45.5 and 45.6 s. No answer content was available to score (0/25). The model is installed and remains on the laptop.
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
| R1 | Qwen2.5 7B Instruct | 37.9 s | 2/25 | 2 answers | 3/5 timeouts; both completed SQL suggestions used nonexistent schema names. |
| R2 | Gemma 3 12B | 45.5 s | 0/25 | — | 5/5 timeouts; no usable answer. Removed after round. |
| R3 | Qwen3 14B | 45.6 s | 0/25 | — | 5/5 timeouts; model kept installed. |
| R4 | — | — | — | — | — |

