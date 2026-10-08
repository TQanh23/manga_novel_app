# Build context is the repo root: the uv workspace and its lockfile live there.
FROM python:3.12.7-slim

COPY --from=ghcr.io/astral-sh/uv:0.12.20 /uv /usr/local/bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_NO_CACHE=1 \
    UV_PYTHON_DOWNLOADS=never \
    PYTHONUNBUFFERED=1 \
    PATH="/srv/.venv/bin:$PATH"

WORKDIR /srv

# Dependencies first, so this layer survives source changes.
COPY pyproject.toml uv.lock .python-version ./
COPY api/pyproject.toml api/pyproject.toml
COPY worker/pyproject.toml worker/pyproject.toml
RUN uv sync --locked --no-dev --package manga-novel-api --no-install-workspace

COPY api api
RUN uv sync --locked --no-dev --package manga-novel-api

RUN useradd --system --uid 10001 --no-create-home app
USER app
WORKDIR /srv/api
EXPOSE 8000

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
