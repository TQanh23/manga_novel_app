# Manga & Novel reading platform

A Ridibooks/KakaoPage-style reading platform for Android and web. The reader side stays thin;
the author side carries the AI and data work (consistency checks over an author's own manuscript,
with a data policy enforced in code).

Status: Phase 0 (foundation) done, Phase 1 (catalogue and novel reader) next. What works today:
register, sign in, roles, and a `ping` job that travels from the API to the worker. See
[IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) and [TASK_CHECKLIST.md](TASK_CHECKLIST.md).

## Layout

```
api/      FastAPI monolith (Python 3.12, uv)
worker/   arq worker for slow and scheduled work
app/      Expo + Expo Router client (Android and web)
infra/    Docker Compose support files, seed data, dashboards (compose.yaml is at the root)
eval/     Fixed AI eval set and runner (empty until Phase 4)
docs/     Design notes
```

## What you need

| Tool | Version | Used for |
|---|---|---|
| Git | any recent | |
| Docker with Compose v2 (`docker compose`) | Docker Desktop on Windows and macOS | The stack, and the backend tests |
| [uv](https://docs.astral.sh/uv/) | 0.12 or newer | Python dependencies. It installs Python 3.12.7 itself from `.python-version`, so you do not need to install Python |
| Node.js with npm | 22 | The client |
| Android Studio emulator, or an Android phone with Expo Go | optional | Running the client on Android |

Docker is enough to run the backend. uv and Node are needed once you run tests or the client.

Commands below are written one per line, so they work in bash and in PowerShell alike.

## Quick start

### 1. Clone

```bash
git clone https://github.com/TQanh23/manga_novel_app.git
cd manga_novel_app
```

### 2. Start the backend

```bash
docker compose up -d
```

No `.env` file is needed: every variable has a development default. The first run pulls images
and builds two, which takes a few minutes. It starts:

| Service | What it is | On your machine |
|---|---|---|
| `postgres` | Postgres 16 + pgvector | `127.0.0.1:5432` |
| `redis` | Cache and job queue | `127.0.0.1:6379` |
| `minio` | S3-compatible storage | `127.0.0.1:9000`, console on http://localhost:9001 (`minioadmin` / `minioadmin`) |
| `minio-init` | One-shot: creates the `raw` and `tiles` buckets | |
| `migrate` | One-shot: applies the Alembic migrations | |
| `seed` | One-shot: creates the development accounts | |
| `api` | FastAPI | http://localhost:8000 |
| `worker` | arq worker | |

`docker compose ps -a` should show `postgres`, `redis`, `minio`, `api` and `worker` as healthy.
`minio-init`, `migrate` and `seed` show `Exited (0)`: they have done their job, that is expected.

### 3. Check it

- http://localhost:8000/readyz answers `{"status":"ok","checks":{"postgres":"ok","redis":"ok"}}`
- http://localhost:8000/docs shows the interactive API docs

### 4. Start the client

```bash
cd app
npm install
npx expo start
```

Press `w` to open the web build at http://localhost:8081. Sign in with one of the accounts below;
you should land on a screen that greets you and lists your roles.

Press `a` to open it on a running Android emulator or a connected device instead (Expo Go).

### Development accounts

The `seed` step creates four accounts, all with the password `local-dev-password`:

| Email | Roles |
|---|---|
| `admin@example.com` | admin |
| `author@example.com` | reader, author |
| `reader1@example.com` | reader |
| `reader2@example.com` | reader |

It leaves existing accounts untouched and refuses to run unless `ENVIRONMENT=local`.

## Working on the backend

Install the Python dependencies once, from the repo root. `api/` and `worker/` are one uv
workspace with a single lockfile and a single `.venv`:

```bash
uv sync --all-packages
```

### Seeing your changes

The `api` and `worker` containers run a copy of the code baked into their images; they do not
watch your files. Pick one:

- Rebuild after a change (also do this after pulling, so new migrations are applied):

  ```bash
  docker compose up -d --build
  ```

- Or run them on your machine against the Compose databases. Stop the containers first, they
  hold port 8000 and would take jobs off the queue:

  ```bash
  docker compose stop api worker
  ```

  ```bash
  cd api
  uv run uvicorn api.main:app --reload
  ```

  ```bash
  cd worker
  uv run python -m worker
  ```

  The API reloads on save. The worker does not; restart it after changing a job.

### Tests

```bash
cd api
uv run pytest
```

```bash
cd worker
uv run pytest
```

Docker has to be running, but the Compose stack does not: the tests start their own throwaway
Postgres (with pgvector) and Redis through Testcontainers. They use a real Postgres on purpose,
because roles, RLS and vector queries are part of what is tested.

To reuse services that are already up instead, which starts faster, create a database for the
tests once and point the tests at it:

```bash
docker compose exec postgres createdb -U postgres manga_novel_test
```

```bash
# bash
export TEST_DATABASE_URL=postgresql+asyncpg://postgres:postgres@127.0.0.1:5432/manga_novel_test
export TEST_REDIS_URL=redis://127.0.0.1:6379/0
```

```powershell
# PowerShell
$env:TEST_DATABASE_URL = "postgresql+asyncpg://postgres:postgres@127.0.0.1:5432/manga_novel_test"
$env:TEST_REDIS_URL = "redis://127.0.0.1:6379/0"
```

These two are read from the shell, not from `.env`. Never point `TEST_DATABASE_URL` at
`manga_novel`: some tests truncate every table. Sharing Redis is safe, the tests write under
their own key prefix.

### Lint and types

From the repo root:

```bash
uv run ruff check .
uv run ruff format --check .
```

Then in `api/` and again in `worker/`:

```bash
uv run mypy .
```

### Migrations

```bash
cd api
uv run alembic upgrade head
uv run alembic revision --autogenerate --rev-id <next number> -m "<message>"
```

Revision ids are sequential; look in `api/migrations/versions/` for the next one. Never edit a
migration that has been applied, add a new one. Migrations run as the owner role
(`MIGRATION_DATABASE_URL`); the API and the worker connect as `app_rw`, a role that owns nothing.

## Working on the client

```bash
cd app
npm run typecheck
npm run lint
npm run gen:api
```

`gen:api` regenerates the TypeScript client in `app/src/api/generated/` from the API's OpenAPI
document. Run it after any API change and commit the result; CI fails when it is stale. It calls
`uv`, so the Python side must be installed. Never write request types by hand.

The client talks to the API at `http://localhost:8000` on web and `http://10.0.2.2:8000` on the
Android emulator (the emulator's name for the host machine). To point it elsewhere, set
`EXPO_PUBLIC_API_URL`, for example in `app/.env.local` (gitignored):

```
EXPO_PUBLIC_API_URL=http://192.168.1.20:8000
```

That is what a physical phone needs: your machine's LAN address, with the phone on the same
network.

UI copy lives in `app/src/i18n/locales/` (English and Vietnamese). ESLint rejects literal text in
JSX, so add a key to both files instead.

## Configuration

Compose and the Python settings both read `.env` at the repo root, and both work without it.
Create one only to override a default; it needs just the lines you change.
[.env.example](.env.example) lists every variable. `.env` is gitignored; never commit it.

The usual reason is a host port that is already taken (a local Postgres on 5432, say). Move the
Compose port, and keep the URLs used by host-side commands in step with it:

```
POSTGRES_PORT=5433
REDIS_PORT=6380
DATABASE_URL=postgresql+asyncpg://app_rw:app_rw@127.0.0.1:5433/manga_novel
MIGRATION_DATABASE_URL=postgresql+asyncpg://postgres:postgres@127.0.0.1:5433/manga_novel
REDIS_URL=redis://127.0.0.1:6380/0
```

Ports the project uses: 5432 Postgres, 6379 Redis, 9000 and 9001 MinIO, 8000 API, 8081 Expo,
11434 Ollama.

Ollama is optional and nothing uses it before Phase 4. `docker compose --profile local-ai up -d`
adds it to the stack.

## Troubleshooting

| Symptom | Cause and fix |
|---|---|
| `docker compose up` fails with "port is already allocated" or "ports are not available" | Something else holds the port. Override it in `.env` (see [Configuration](#configuration)). |
| Host-side `uvicorn`, `alembic` or the worker gets `password authentication failed for user "app_rw"` | It reached a different Postgres on 5432, or `POSTGRES_PORT` was changed without updating `DATABASE_URL` and `MIGRATION_DATABASE_URL`. |
| Connections from the host take about two seconds each on Windows | Use `127.0.0.1` in the URLs, not `localhost`. Compose publishes on IPv4 only and `localhost` tries IPv6 first. |
| A backend change does not show up | The containers run the image, not your files. See [Seeing your changes](#seeing-your-changes). |
| `uv run pytest` fails before any test runs with a Docker connection error | Docker is not running; Testcontainers needs it. |
| The web app reports a network error although the API is up | The API only allows the origin `http://localhost:8081`. Open the app at that exact address (not `127.0.0.1`, not another port), or set `CORS_ORIGINS` in `.env` and run `docker compose up -d api`. |
| Sign-in answers "Too many attempts" | Auth routes are rate limited: 5 sign-in attempts per account and 30 requests per IP per minute. Wait a minute. |
| A phone cannot reach the API | Set `EXPO_PUBLIC_API_URL` to your machine's LAN address and let port 8000 through the firewall. |
| CI fails on "Generated API client is up to date" | Run `npm run gen:api` in `app/` and commit `openapi.json` and `src/api/generated/`. |

To start over with empty data:

```bash
docker compose down -v
```

This deletes the local database and everything in MinIO. The next `docker compose up -d`
recreates the schema and the development accounts.

## Before you open a PR

CI runs three jobs on every pull request, and you can run each locally:

- **backend**: `ruff check`, `ruff format --check`, `mypy` and `pytest` for `api/` and `worker/`
- **compose**: a fresh `docker compose up -d --build`, then a seeded admin signs in and a job
  reaches the worker
- **app**: the generated client is up to date, `npm run typecheck`, `npm run lint`

Branches are named `phase-<n>/<topic>`. Commit messages and PR descriptions name the task from
[TASK_CHECKLIST.md](TASK_CHECKLIST.md) and the requirement ID it serves, for example
`(Phase 0: 0.5)` or `FR-PAY-02`, so work traces back to a requirement.

## How it works

The API writes one JSON object per log line, each carrying the request's `X-Request-ID`. Content
fields (`text`, `content`, `prompt`, ...) are masked before a line is written. `/healthz` reports
that the process is up, `/readyz` that Postgres and Redis answer, and `/metrics` serves request
latency for Prometheus. Errors share one shape: `{"error": {"code", "message", "request_id",
"details"}}`.

On web the refresh token is an httpOnly cookie and the access token stays in memory; on Android
the refresh token is kept in SecureStore. Either way the app signs back in silently on start.

Slow work never runs in the API. An endpoint calls `enqueue(kind, target_id, content_hash)` and
answers `202` with a job id; the worker runs it. Asking again for the same work on the same input
is the same job. A job that fails is retried three times with backoff, then recorded in the
`dead-letter` list in Redis. Its log lines carry the request id of the API call that asked for it.

## Where to read next

- [CLAUDE.md](CLAUDE.md): architecture rules, the money and AI data policies, conventions. Read
  it before your first change; it also links the system spec and the PRD, which define the
  requirement IDs.
- [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md): phases, build order, exit checks.
- [TASK_CHECKLIST.md](TASK_CHECKLIST.md): what is done and what is next.
- [.claude/skills/](.claude/skills/): step-by-step checklists for adding an endpoint, a
  migration, a worker job, or changing billing or AI code.
