---
title: Three portfolio projects you can build for almost no money
part: Appendix
summary: Android to AI engineering. Three projects that reuse this course, cost nothing to run, and give you real things to talk about in interviews.
---

**After ten years of Android, hiring managers already believe you can ship. What they want to see is that you can build the AI side: retrieval, model calls, queues, evaluation, and cost control. These three projects show exactly that, and none of them needs a server bill.**

In this appendix, we will learn:

- What a good AI-engineering portfolio project looks like
- Three projects, each with a scope, a free stack, and what to measure
- Which free tiers are real, and which limits can surprise you
- How to present a project when you cannot keep a server running forever

Let's get started.

## What makes a project worth showing

A recruiter will open your repository for a minute or two. They look for four things:

1. **A problem in one sentence.** "Answers questions about the Android docs, with the source of each answer."
2. **A picture of the architecture.** One diagram. You already know how to draw one from this course.
3. **Numbers.** How many test questions did it answer correctly? How long did it take? How many model calls did it make? One real number beats five adjectives.
4. **A one-command way to run it** and a short video or GIF for people who will not run it.

!!! android "Android parallel"
    This is the same as a good Play Store listing: a clear description, screenshots, and proof that it works. Your Android experience is an advantage here, because you know what "ready to ship" feels like.

## The free ingredients, and their real limits

Every limit below comes from the provider's own page, read on 14 November 2026. Free tiers change, so check the page before you depend on one.

| Ingredient | What you get for free | Catch |
|---|---|---|
| **Ollama** on your laptop | Run open models locally. API on `http://localhost:11434`. It can also make embeddings through `/api/embed`. | Uses your CPU, GPU and disk. Models can be tens of GB. |
| **Gemini API** free tier | Many models, including the embedding models, list "Free of charge" input and output on the pricing page. | The pricing page says free-tier content is "used to improve our products". Never send private data. Limits are shown per account in Google AI Studio. |
| **Neon** free Postgres | 1 GB per project, 100 compute-hours per project per month. Has the `pgvector` extension. | Sleeps after 5 minutes idle. When the hours run out, compute is suspended until the next period. |
| **Supabase** free | Two free projects, 500 MB database each. | Small database. |
| **GitHub Pages** | Turns a repository into a live website. | Static pages only. |
| **Cloudflare Workers** free | 100,000 requests per day, 10 ms of CPU time per invocation. | Tiny CPU budget. Good for a thin proxy, not for heavy work. |
| **GitHub Codespaces** | 120 compute-hours and 15 GB-month per month for a free account. | A monthly cap. |
| **Hugging Face Spaces** | Static Spaces are free. | The Hub's page says Gradio and Docker Spaces need a paid plan to create. Many older tutorials say otherwise. |

!!! warning "Do not put an API key in your repository"
    Keep keys in a `.env` file that is in `.gitignore`, and commit a `.env.example` with fake values. A leaked key on a public repository is the fastest way to turn "free" into a surprise.

## Project 1: "Ask the docs", retrieval-augmented answers on Postgres

**The idea.** You ask a question in plain English. The system finds the most relevant pieces of a documentation set and gives them to a language model, which answers and tells you which pieces it used. This is called RAG (retrieval-augmented generation).

**Why it suits you.** You pick documentation you know deeply: the Android developer docs, or the Jetpack Compose and Room guides. You can judge whether the answers are correct, which most people building RAG demos cannot.

**Free stack.**

- **Embeddings:** Ollama on your laptop. Its documentation describes embeddings as turning text into numeric vectors you can store and search with cosine similarity, and shows `POST /api/embed` and `ollama.embed(...)` for it. The Gemini embedding models are an alternative, since they list a free tier.
- **Storage and search:** Postgres with `pgvector`. Neon's documentation shows `CREATE EXTENSION IF NOT EXISTS vector;`, a column such as `embedding VECTOR(3)`, and `<=>` for cosine distance. You already know Postgres from this course.
- **Answering:** a local Ollama model, or the Gemini free tier.
- **API:** FastAPI, the same as chapter 9.

**Steps.**

1. Download 50 to 200 pages of documentation as text. Only use documentation you are allowed to copy, and keep each page's URL.
2. Split each page into pieces of a few paragraphs. Store `(url, piece_text, embedding)` in one table.
3. Write `POST /ask`: embed the question, run a `SELECT ... ORDER BY embedding <=> :question_vector LIMIT 5`, and send those pieces to the model with the instruction "answer only from these pieces and name the URL".
4. Return the answer and the list of source URLs.

**The part that makes it a portfolio piece: measure it.**

- Write 30 test questions yourself, each with the correct source page.
- Measure how often the right page appears in the top 5 (this is "recall at 5").
- Change one thing (piece size, number of pieces) and measure again. Put the table in the README.

Most demos skip this step. Doing it is what an AI-engineering interviewer wants to hear about.

**Cost.** Zero if both models run on your laptop. The database fits in Neon's free 1 GB for a few thousand pieces. Check the size before you promise that.

## Project 2: an event-driven AI pipeline (the capstone of this course)

**The idea.** A support inbox for the ChaiPoint app. New customer messages arrive through an API. Each message is stored together with an event, in one transaction (the outbox, chapter 11). Workers pick events up safely (chapter 12), ask a model to label each message (complaint, refund request, question, praise) and write a one-line summary, and save the result. A small page lists the results.

**Why it suits you.** It combines what this course teaches with the AI part. It answers the question "can you build reliable systems around a model?", which is much of the job. Models are slow, fail, and sometimes return nonsense. That is exactly the situation queues, retries and dead-letter tables were made for.

**Free stack.**

- FastAPI, PostgreSQL (your laptop or Neon), the outbox and workers from Part 3.
- Model: Ollama locally, or the Gemini free tier.
- Interface: a static page on GitHub Pages that shows a **recorded sample run** (see "Presenting it" below).

**Steps.**

1. Reuse the order service structure from chapter 9: `POST /messages` stores the message and the event in one transaction.
2. The worker claims events with `FOR UPDATE SKIP LOCKED` (chapter 12), calls the model, validates the answer against a small schema (only the four allowed labels), and saves it.
3. If the answer is invalid or the model call fails, retry a limited number of times, then move the event to a dead-letter table you can query.
4. Never trust the model's text: check it, and treat the message text as data, never as instructions.

**What to measure and show.**

- Run 200 sample messages through with two workers. Report how many succeeded, how many were retried, how many went to the dead-letter table, and the average time per message.
- Kill a worker half-way. Show that no message is lost or processed twice. This is the best demo you can have.
- Count model calls per message. This is your cost number, even when the price is zero today.

**Cost.** Zero with a local model. With a free tier, respect its limits: the account's current limits are shown in Google AI Studio, so read them there and set the worker's speed below them.

## Project 3: an Android app with on-device AI

**The idea.** An Android app where the AI runs on the phone, so every call costs nothing. For example, a notes app that summarizes a long note into bullet points and rewrites a rough message in a friendlier tone.

**Why it suits you.** This is your home ground, and it shows you can bring AI into a product, not only into a backend. Google's ML Kit GenAI APIs use Gemini Nano to run generative tasks on the device. The documentation lists summarization (articles or chat conversations as a bulleted list), proofreading, rewriting and image description, and says they run entirely on-device, keep working without a reliable internet connection, and add no server cost per call.

!!! warning "Check your phone first"
    The documentation says these APIs are available only on a list of supported devices, with plans to add more, and that language support depends on the device. Open the ML Kit GenAI page and compare the list with the phone or emulator you have, before you plan the project around it. I did not capture the device list, so do not assume yours is on it.

**Free stack.**

- Kotlin, Jetpack Compose, Room (what you already know) plus the ML Kit GenAI dependency from the official guide.
- Optional: sync notes to the FastAPI backend from this course, running on your laptop.
- Distribution: a screen recording and a signed APK attached to a GitHub release, instead of a paid store listing.

**What to measure and show.**

- A short screen recording of a note being summarized with the phone in airplane mode. That one clip proves the "no server" claim.
- A README section on what happens when the model is not available on a device: your fallback behaviour is the interesting engineering.

**Cost.** Zero.

## Presenting a project when you cannot keep a server running

A free database sleeps and a free model has limits, so a live demo link can break at the worst moment. Plan for that:

- Make **one-command local setup** the main way to run it: a README with the exact commands.
- Record a **2 minute video** or a GIF of a full run, and put it at the top of the README.
- Put the **sample outputs and your measurements** in the repository, so the evidence is there even when nothing is running.
- If you want a live page, host a static page on GitHub Pages that replays a recorded sample run. A static page costs nothing and cannot run out of quota.

## Which one first?

If you build one, build **Project 2**: it uses the most of this course and shows the engineering judgement hiring teams look for. Build **Project 1** next, because retrieval is the most common AI task in job descriptions. Build **Project 3** if you want the story "Android engineer who ships AI features into apps".

## Summary

- A strong project has a one-line problem, one diagram, real numbers and a one-command run.
- Project 1: documentation question-answering with `pgvector`, measured with your own test questions.
- Project 2: an event-driven pipeline where workers label messages with a model, with retries, a dead-letter table, and a "kill a worker" demo.
- Project 3: an Android app using on-device Gemini Nano through ML Kit GenAI, with no per-call cost, on supported devices.
- Free tiers have real limits. Read the provider's page, and never send private data to a free tier that says it uses content to improve products.

!!! faq "Do I need a GPU?"
    Not to start. Ollama can run on CPU, slower. Small models answer slowly on a laptop but they work. The Gemini free tier is the alternative when your laptop is too slow, with the privacy catch above.

!!! faq "Will free tiers still be free next month?"
    Not guaranteed. The Gemini pricing page itself shows rates changing on 1 January 2027 for paid use, and Hugging Face's Spaces rules differ from many older tutorials. That is why the plan is to run everything locally and keep recordings.

## Sources

- [Ollama: Embeddings](https://docs.ollama.com/capabilities/embeddings)
- [Ollama: Windows](https://docs.ollama.com/windows)
- [Gemini API pricing](https://ai.google.dev/gemini-api/docs/pricing)
- [Gemini API rate limits](https://ai.google.dev/gemini-api/docs/rate-limits)
- [Neon: the pgvector extension](https://neon.com/docs/extensions/pgvector)
- [Neon plans](https://neon.com/docs/introduction/plans)
- [Supabase: About billing](https://supabase.com/docs/guides/platform/billing-on-supabase)
- [GitHub Pages documentation](https://docs.github.com/en/pages)
- [Cloudflare Workers pricing](https://developers.cloudflare.com/workers/platform/pricing/)
- [GitHub Docs: Codespaces billing](https://docs.github.com/en/billing/concepts/product-billing/github-codespaces)
- [Hugging Face: Spaces overview](https://huggingface.co/docs/hub/spaces-overview)
- [ML Kit GenAI APIs overview](https://developers.google.com/ml-kit/genai)

That's it for now.
