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
infra/    Docker Compose support files, seed data, dashboards
eval/     Fixed AI eval set and runner
docs/     Design notes
```

## Development

Requires [uv](https://docs.astral.sh/uv/) and Node 22. uv installs Python 3.12.7 from
`.python-version`.

```bash
uv sync --all-packages

cd api && uv run pytest
cd api && uv run ruff check . && uv run mypy .
cd api && uv run uvicorn api.main:app --reload

cd app && npm install
cd app && npx expo start          # press w for web, a for Android
cd app && npm run typecheck && npm run lint
```

Conventions and architecture rules are in [CLAUDE.md](CLAUDE.md).
