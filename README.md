# Manga & Novel reading platform

A Ridibooks/KakaoPage-style reading platform for Android and web. The reader side stays thin;
the author side carries the AI and data work (consistency checks over an author's own manuscript,
with a data policy enforced in code).

Status: Phase 0 (foundation) in progress. See [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md)
and [TASK_CHECKLIST.md](TASK_CHECKLIST.md).

## Layout

```
api/      FastAPI monolith (Python 3.12, uv)
worker/   arq worker for slow and scheduled work
app/      Expo + Expo Router client (Android and web)
infra/    Docker Compose support files, seed data, dashboards (compose.yaml is at the root)
eval/     Fixed AI eval set and runner
docs/     Design notes
```

## Development

Requires Docker, [uv](https://docs.astral.sh/uv/) and Node 22. uv installs Python 3.12.7 from
`.python-version`.

```bash
docker compose up                         # Postgres+pgvector, Redis, MinIO, migrations, seed accounts, api on :8000, worker
docker compose --profile local-ai up      # the same plus Ollama

uv sync --all-packages

cd api && uv run pytest                   # starts its own Postgres and Redis through Testcontainers
cd worker && uv run pytest
cd api && uv run ruff check . && uv run mypy .
cd api && uv run alembic upgrade head     # against the Compose Postgres
cd api && uv run uvicorn api.main:app --reload

cd app && npm install
cd app && npx expo start          # press w for web, a for Android
cd app && npm run typecheck && npm run lint
cd app && npm run gen:api         # after any API change: regenerate the TS client and commit it
```

`docker compose up` creates four accounts for development, all with the password
`local-dev-password`:

| Email | Roles |
|---|---|
| `admin@example.com` | admin |
| `author@example.com` | reader, author |
| `reader1@example.com` | reader |
| `reader2@example.com` | reader |

The seed step leaves existing accounts untouched and refuses to run unless `ENVIRONMENT=local`.

The client talks to the API at `http://localhost:8000` on web and `http://10.0.2.2:8000` on the
Android emulator (the emulator's name for the host machine). Set `EXPO_PUBLIC_API_URL` to point it
elsewhere, for example at your machine's LAN address when testing on a phone.

No `.env` file is needed. If a host port is already taken, copy [.env.example](.env.example) to
`.env` and change it there. The API connects to Postgres as `app_rw`, a role that owns nothing;
migrations run as the owner role.

The API writes one JSON object per log line, each carrying the request's `X-Request-ID`. Content
fields (`text`, `content`, `prompt`, ...) are masked before a line is written. `/healthz` reports
that the process is up, `/readyz` that Postgres and Redis answer, and `/metrics` serves request
latency for Prometheus. Errors share one shape: `{"error": {"code", "message", "request_id",
"details"}}`.

On web the refresh token is an httpOnly cookie and the access token stays in memory; on Android
the refresh token is kept in SecureStore. Either way the app signs back in silently on start. UI
copy lives in `app/src/i18n/locales/` (English and Vietnamese); ESLint rejects literal text in JSX.

Slow work never runs in the API. An endpoint calls `enqueue(kind, target_id, content_hash)` and
answers `202` with a job id; the worker (`python -m worker`) runs it. Asking again for the same
work on the same input is the same job. A job that fails is retried three times with backoff, then
recorded in the `dead-letter` list in Redis. Its log lines carry the request id of the API call
that asked for it.

To run the tests against services that are already up instead of Testcontainers, set
`TEST_DATABASE_URL` and `TEST_REDIS_URL` (see [.env.example](.env.example)).

Conventions and architecture rules are in [CLAUDE.md](CLAUDE.md).
