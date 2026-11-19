# T32 — CI and GitHub Pages verification

## Scope

- CI runs on pull requests to `main`, pushes to `main`, and manual dispatch.
- The app job installs the existing Python requirements and locked npm dependencies, builds the course and Vite assets before Python tests, and runs the sandbox/exercise JavaScript suites.
- A separate job starts PostgreSQL 16 with a fixed disposable `course_test` database, runs every executable course SQL block, then runs the demo API tests from `project/`.
- CI has only `contents: read`; checkouts do not persist credentials. Pages grants `pages: write` and `id-token: write` only to the deployment job.

## Database reset safety

Both SQL verification paths erase the public schema. They now read the connected database name before destructive SQL and refuse any name without an `_test` suffix. This replaces the demo fixture's DSN-text check, which could be bypassed by a connection-string override. No-database regression tests assert that an unsafe resolved target or a failed connection never reaches the reset command.

The suffix is an accident-prevention guard, not permission to use an important database named `_test`. CI uses only its fresh service database and no external database secrets.

## Pages evidence — November 19, 2026

`GET /repos/SumukhaK/postgres-event-driven-for-android-devs/pages` reported `build_type: workflow`, `public: true`, and `https_enforced: true`. The [published course](https://sumukhak.github.io/postgres-event-driven-for-android-devs/) returned HTTP 200 and the expected course title. README setup wording now reflects the active deployment.

Pages serves the static course. This verification does not establish a public Developer Studio backend, account sync, or AI provider availability.

## Validation

GitHub job results will be recorded after the PR run. No local Docker/WSL startup or live provider/model request is part of this task.
