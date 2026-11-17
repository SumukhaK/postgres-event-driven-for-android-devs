# Postgres and Event-Driven Backends for Android Developers

A hands-on course for an Android developer (Kotlin, Room, a little Python and FastAPI) who wants to learn SQL, PostgreSQL and event-driven backends. Written in a simple, step-by-step style with animated diagrams.

## Developer Studio

The course site uses a dark, code-first workspace with lessons, runnable examples, and contextual help.

![Developer Studio learning workspace](screenshots/developer-studio.png)

GitHub Pages hosts the static reading course. The full-stack Developer Studio adds account-backed progress, the PostgreSQL sandbox, and optional AI help. After starting it locally, [open Developer Studio](http://127.0.0.1:8000/).

- [Run locally with Docker Compose](learning_app/README.md#run-with-docker-compose)
- [Run directly on your machine for ChatGPT plan sign-in](learning_app/README.md#run-directly-on-your-machine)
- [Connect GPT, Claude, and OpenCode providers](learning_app/README.md#connect-cloud-ai-providers)

Read it online: https://sumukhak.github.io/postgres-event-driven-for-android-devs/ (after GitHub Pages is switched to "GitHub Actions").

- Chapters are Markdown files in `src/`. `python tools/build.py` turns them into the site in `site/`.
- Every SQL example is run against a real PostgreSQL 16 by `python tools/run_sql.py` before it is published.
- Each chapter ends with a Sources list of official documentation.

## Course contents

| Chapter | Subject | What you'll learn |
| --- | --- | --- |
| [00 · Start here](src/00-start-here.md) | Course orientation | What you will build and how to use the lessons and playgrounds |
| [01 · From Room to Postgres](src/01-from-room-to-postgres.md) | Data storage | How local Room data maps to a PostgreSQL-backed application |
| [02 · Tables, rows, and types](src/02-tables-rows-types.md) | Data modeling | Designing tables, columns, and types for the ChaiPoint database |
| [03 · Asking questions with SELECT](src/03-select.md) | Querying | Reading and filtering data with `SELECT` |
| [04 · Changing data](src/04-changing-data.md) | Data changes | Using `UPDATE`, `DELETE`, and upsert safely |
| [05 · JOINs](src/05-joins.md) | Relationships | Combining related tables in a query |
| [06 · Aggregates](src/06-aggregates.md) | Summaries | Counting, summing, and grouping query results |
| [07 · Indexes and EXPLAIN](src/07-indexes-explain.md) | Query performance | Understanding indexes and investigating slow queries |
| [08 · Transactions and concurrency](src/08-transactions-concurrency.md) | Correctness | Handling simultaneous work with transactions and concurrency control |
| [09 · FastAPI and Postgres](src/09-fastapi-postgres.md) | Backend integration | Connecting a FastAPI application to PostgreSQL safely |
| [10 · Event-driven thinking](src/10-event-driven-thinking.md) | Event-driven systems | Telling the rest of a system what happened |
| [A1 · Windows install guide](src/A1-install-windows.md) | Setup | Installing the tools and finding no-install playgrounds |
| [A2 · Portfolio projects](src/A2-portfolio-projects.md) | Practice projects | Building three low-cost projects to demonstrate what you learned |

## Developer Studio AI assistant experiment

The initial comparison exposed a playground timeout/configuration bug; those timeout observations are not counted as model scores. A follow-up code trial adds the sandbox's relevant table/column schema and verified exercise references to assistant context, plus concise-answer and safe-SQL instructions. Scores are out of 25: correctness, explanation usefulness, and avoiding unsupported claims.

| Model | Run | Mean answer latency | Completed | Score | Summary |
| --- | --- | ---: | ---: | ---: | --- |
| Qwen2.5 7B Instruct (`qwen2.5:7b-instruct`) | Baseline | 37.1 s | 5/5 | 10/25 | Frequent schema mistakes; outbox answer misstated the transaction boundary. |
| Qwen2.5 7B Instruct (`qwen2.5:7b-instruct`) | Schema/reference context trial | 9.6 s | 5/5 | 25/25 | All five answers matched the exercise schema and expected concepts. |
| Qwen3 14B (`qwen3:14b`) | Baseline | 59.2 s | 5/5 | 16/25 | Better explanations, but schema mistakes remained. |
| Qwen3 14B (`qwen3:14b`) | Schema/reference context trial | 29.2 s | 5/5 | 25/25 | All five answers matched the exercise schema and expected concepts. |
| ChatGPT plan (`gpt-6.1-sol`) | Baseline | 9.2 s | 5/5 | 22/25 | One incorrect column name; other answers matched the lesson schema and concepts. |
| ChatGPT plan (`gpt-6.1-sol`) | Schema/reference context trial | 4.5 s | 5/5 | 25/25 | All five answers matched the verified exercise solutions and explanations. |

In this small trial, Qwen2.5 7B improved by 15 points and averaged 27.5 seconds faster; Qwen3 14B improved by 9 points and averaged 30.0 seconds faster; ChatGPT improved by 3 points and averaged 4.7 seconds faster. The GPT retest averaged 4.50 s after a 3.45 s warm-up. These are not controlled model-only comparisons: optimized prompts include verified exercise references, the earlier literal prompts were not retained and were reconstructed from exercise descriptions, and machine/network conditions differed between runs. Treat the improvements as promising, not conclusive. Accuracy remains the priority on this 4 GB GPU / 16 GB RAM laptop. See the [full prompts, per-prompt latencies, and scoring notes](tasks/local-model-evaluation.md).

### Output-limit and residency follow-up (T26)

On November 16–17, 2026, each local model completed 24 native Ollama requests with app-built context. A 160-token hint/nudge ceiling showed no repeatable benefit over 500; **production settings remain unchanged**. Immediate reuse avoided model reload and reduced prompt processing:

| Model | Cold → warm mean, same explanation | Minimum free system RAM | Completed / truncated |
| --- | ---: | ---: | ---: |
| Qwen2.5 7B | 27.021 → 13.218 s | 1.96 GiB | 24 / 0 |
| Qwen3 14B | 46.753 → 19.924 s | 1.51 GiB | 24 / 0 |

Each residency mean covers two requests. Both models were unloaded afterward. Different background apps were open on each day, so this is not a controlled model ranking. The new mixed-action fixture also exposed an overly prescriptive 7B nudge and a misleading 14B index explanation; quality did not improve with the lower cap. See [the full report and raw answers](tasks/t26-tuning-results.md) for manual scoring, budget comparisons, and limitations. GPT and browser paint timing were outside this local tuning trial.
