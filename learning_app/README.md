# Postgres Lab · Developer Studio

The full-stack learning app serves lessons, accounts and progress, the browser PostgreSQL sandbox, and optional AI help. It is separate from the ChaiPoint order API in `project/app/`. GitHub Pages serves only static course pages; it does not provide accounts, progress sync, or AI.

## Run with Docker Compose

From the repository root, create a local environment file and generate a Fernet key:

```powershell
Copy-Item .env.example .env
python -c "import base64, os; print(base64.urlsafe_b64encode(os.urandom(32)).decode())"
```

Paste the generated value after `LEARNING_CREDENTIAL_KEY=` in `.env`. Keep that key safe and stable: changing it makes saved provider credentials unreadable. `.env` is ignored by Git.

Build and start the app:

```powershell
docker compose up --build -d
docker compose ps
```

Open `http://localhost:8000/`. Set `LEARNING_PORT` in `.env` to use another host port. View logs with `docker compose logs -f app`; stop the app with `docker compose down`. Its SQLite database lives in the persistent `learning-data` volume at `/data/learning.sqlite3`.

## Connect a local model

Sign in, open **AI connections → Local model**, and enter the server's OpenAI-compatible base URL. The server must provide `/v1/models` and `/v1/chat/completions`. An API key is optional and, when supplied, is encrypted per account. Replacing an endpoint with the key field blank removes its saved key.

With Docker Compose, use the host gateway name so the app container can reach a model server on your machine:

| Server | Base URL in Developer Studio |
| --- | --- |
| Ollama | `http://host.docker.internal:11434/v1` |
| vLLM | `http://host.docker.internal:8000/v1` |

The Compose service maps `host.docker.internal` to the host gateway (Docker Desktop provides this name automatically). For a direct Uvicorn run, use `http://127.0.0.1:11434/v1` for Ollama or `http://127.0.0.1:8000/v1` for vLLM. Other OpenAI-compatible local servers work with their own port and `/v1` base path. The app accepts loopback addresses and `host.docker.internal`; it rejects LAN or public hosts.

## Back up, restore, or reset

Back up the live SQLite database and copy it to the repository folder:

```powershell
docker compose exec -T app python -c "import sqlite3; s=sqlite3.connect('/data/learning.sqlite3'); b=sqlite3.connect('/data/backup.sqlite3'); s.backup(b); b.close(); s.close()"
docker compose cp app:/data/backup.sqlite3 ./learning.sqlite3.backup
docker compose exec -T app rm /data/backup.sqlite3
```

Keep the backup file and `LEARNING_CREDENTIAL_KEY` together in a secure location. To restore, stop the app, copy the backup over the database, and start it again:

```powershell
docker compose stop app
docker compose cp ./learning.sqlite3.backup app:/data/learning.sqlite3
docker compose start app
```

To erase all local accounts, progress, and provider connections, run `docker compose down --volumes`. This deletes the database volume; back it up first if you need to keep anything.

## Run directly on your machine

This path supports ChatGPT plan sign-in, which requires a loopback app and browser connection. Install dependencies and build both course and app assets from the repository root:

```powershell
python -m pip install -r project/requirements.txt
npm ci
python tools/build.py
npm run build
$env:LEARNING_CREDENTIAL_KEY = "<generated Fernet key>"
$env:LEARNING_DB_PATH = "data/learning.sqlite3"
python -m uvicorn learning_app.main:app --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000/`. The health check is `/api/health`; built lessons are served under `/course/`.

## Backend hosting notes

- Keep the app on one instance with a persistent disk mounted at `/data`; this app uses SQLite and is not configured for horizontal scaling.
- For a public host, terminate HTTPS at a trusted reverse proxy and set `LEARNING_COOKIE_SECURE=1`. Keep `.env`, the encryption key, and SQLite backups private.
- ChatGPT plan sign-in is loopback-only. The Docker bridge connection is not loopback to the app, so use direct local Uvicorn for that provider. API-key provider connections work with Docker Compose.
- A hosted backend is separate from GitHub Pages. This repository does not include a deployed backend host or public deployment configuration.

Account storage, interactive exercises, and AI provider connections are tracked in [`../tasks/todo.md`](../tasks/todo.md).

## Connect cloud AI providers

After signing in to Developer Studio, open **AI connections**. The supported account and billing options are:

| Provider | Connection | Where usage is billed |
| --- | --- | --- |
| ChatGPT plan | Local **Continue with ChatGPT** sign-in for eligible accounts | Your ChatGPT plan allocation |
| OpenAI API | OpenAI API key | OpenAI API account; separate from a ChatGPT subscription |
| Claude | Anthropic Console API key | Anthropic Console credits or API billing; Claude.ai subscriptions do not include Console API usage ([billing details](https://support.anthropic.com/en/articles/9876003-i-subscribe-to-a-paid-claude-ai-plan-why-do-i-have-to-pay-separately-for-api-usage-on-console)) |
| OpenCode Console | OpenCode Console API key | The Console workspace budget or Go plan; some free models are only available inside OpenCode |

This app connects Claude and OpenCode through their documented inference APIs and keys. It does not reuse tokens from Claude Code or the OpenCode CLI.
