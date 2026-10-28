#!/bin/bash
# Claude Code cloud sessions: install dependencies and start the services the
# tests need. Cloud containers have no Docker daemon, so Testcontainers cannot
# run; this starts a native Postgres 16 + pgvector and Redis instead and points
# the test fixtures at them through TEST_DATABASE_URL / TEST_REDIS_URL, the
# same variables CI sets.
set -euo pipefail

if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

cd "$CLAUDE_PROJECT_DIR"

TEST_DB=manga_novel_test

# Postgres 16 is preinstalled in the image; pgvector is not.
if [ ! -f /usr/share/postgresql/16/extension/vector.control ]; then
  apt-get update -qq
  DEBIAN_FRONTEND=noninteractive apt-get install -y -qq postgresql-16-pgvector >/dev/null
fi

if ! pg_isready -q -h 127.0.0.1 -p 5432; then
  pg_ctlcluster 16 main start
  for _ in $(seq 1 30); do
    pg_isready -q -h 127.0.0.1 -p 5432 && break
    sleep 1
  done
fi
# Same credentials as the CI service container.
su postgres -c "psql -q -c \"ALTER USER postgres PASSWORD 'postgres'\""
if ! su postgres -c "psql -tAc \"SELECT 1 FROM pg_database WHERE datname = '$TEST_DB'\"" | grep -q 1; then
  su postgres -c "createdb $TEST_DB"
fi

if ! redis-cli -h 127.0.0.1 ping >/dev/null 2>&1; then
  redis-server --daemonize yes --bind 127.0.0.1 --port 6379 --save '' --appendonly no >/dev/null
fi

# Python: one uv workspace for api/ and worker/.
uv sync --all-packages --locked --quiet

# Client: npm install rather than npm ci so the cached container is reused.
if [ -f app/package.json ]; then
  (cd app && npm install --no-audit --no-fund --loglevel=error)
fi

{
  echo "export TEST_DATABASE_URL=postgresql+asyncpg://postgres:postgres@127.0.0.1:5432/$TEST_DB"
  echo "export TEST_REDIS_URL=redis://127.0.0.1:6379/0"
} >> "$CLAUDE_ENV_FILE"
