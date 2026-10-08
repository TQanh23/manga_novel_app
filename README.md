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
docker compose up                         # Postgres+pgvector, Redis, MinIO, migrations, api on :8000
docker compose --profile local-ai up      # the same plus Ollama

uv sync --all-packages

cd api && uv run pytest                   # starts its own Postgres and Redis through Testcontainers
cd api && uv run ruff check . && uv run mypy .
cd api && uv run alembic upgrade head     # against the Compose Postgres
cd api && uv run uvicorn api.main:app --reload

cd app && npm install
cd app && npx expo start          # press w for web, a for Android
cd app && npm run typecheck && npm run lint
```

No `.env` file is needed. If a host port is already taken, copy [.env.example](.env.example) to
`.env` and change it there. The API connects to Postgres as `app_rw`, a role that owns nothing;
migrations run as the owner role.

The API writes one JSON object per log line, each carrying the request's `X-Request-ID`. Content
fields (`text`, `content`, `prompt`, ...) are masked before a line is written. `/healthz` reports
that the process is up, `/readyz` that Postgres and Redis answer, and `/metrics` serves request
latency for Prometheus. Errors share one shape: `{"error": {"code", "message", "request_id",
"details"}}`.

To run the tests against services that are already up instead of Testcontainers, set
`TEST_DATABASE_URL` and `TEST_REDIS_URL` (see [.env.example](.env.example)).

Conventions and architecture rules are in [CLAUDE.md](CLAUDE.md).
