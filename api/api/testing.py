"""Shared pytest fixtures, loaded as a plugin by api/conftest.py and worker/conftest.py.

Tests run against a real Postgres with pgvector and a real Redis, connecting as
app_rw like the running API does.
"""

import io
import json
import logging
import os
from collections.abc import AsyncIterator, Callable, Iterator
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from redis.asyncio import Redis
from sqlalchemy import make_url
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from api.core.config import Settings, get_settings
from api.core.db import get_engine, get_session, get_sessionmaker
from api.core.logging import build_handler, configure_logging
from api.core.redis import get_redis

API_DIR = Path(__file__).resolve().parents[1]
POSTGRES_IMAGE = "pgvector/pgvector:pg16"
REDIS_IMAGE = "redis:7-alpine"


def _alembic_config(database_url: str | None = None) -> Config:
    config = Config(API_DIR / "alembic.ini")
    if database_url is not None:
        config.attributes["database_url"] = database_url
    return config


@pytest.fixture(scope="session")
def alembic_config() -> Callable[..., Config]:
    """Builds an Alembic config; pass a URL to migrate a database other than the shared one."""
    return _alembic_config


@pytest.fixture(scope="session")
def owner_database_url() -> Iterator[str]:
    """URL of the role that runs migrations.

    CI sets TEST_DATABASE_URL to its service container. Without it a throwaway
    pgvector container is started, which needs a running Docker daemon.
    """
    if url := os.environ.get("TEST_DATABASE_URL"):
        yield url
        return

    from testcontainers.community.postgres import PostgresContainer

    with PostgresContainer(POSTGRES_IMAGE, driver="asyncpg") as postgres:
        yield postgres.get_connection_url()


@pytest.fixture(scope="session")
def redis_url() -> Iterator[str]:
    """CI sets TEST_REDIS_URL; without it a throwaway Redis container is started."""
    if url := os.environ.get("TEST_REDIS_URL"):
        yield url
        return

    from testcontainers.community.redis import RedisContainer

    with RedisContainer(REDIS_IMAGE) as container:
        host = container.get_container_host_ip()
        yield f"redis://{host}:{container.get_exposed_port(6379)}/0"


@pytest.fixture(scope="session")
def settings(owner_database_url: str, redis_url: str) -> Iterator[Settings]:
    """Point the app at the test database and Redis, connecting as app_rw like the real API."""
    # Roles are cluster-wide: keep the configured password so that running the
    # tests against the Compose Postgres does not lock the dev stack out.
    password = Settings().app_rw_password.get_secret_value()
    app_url = make_url(owner_database_url).set(username="app_rw", password=password)

    with pytest.MonkeyPatch.context() as patch:
        patch.setenv("MIGRATION_DATABASE_URL", owner_database_url)
        patch.setenv("DATABASE_URL", app_url.render_as_string(hide_password=False))
        patch.setenv("REDIS_URL", redis_url)
        # The Redis may be shared with a dev stack, so this run gets its own
        # namespace and only ever deletes keys inside it.
        patch.setenv("REDIS_KEY_PREFIX", f"test-{uuid4().hex}:")
        get_settings.cache_clear()
        yield get_settings()

    get_settings.cache_clear()


@pytest.fixture(scope="session")
def migrated(settings: Settings) -> None:
    # Alembic's env.py calls asyncio.run, so this has to stay a sync fixture.
    command.upgrade(_alembic_config(), "head")


@pytest.fixture(scope="session")
async def engine(migrated: None) -> AsyncIterator[AsyncEngine]:
    get_engine.cache_clear()
    get_sessionmaker.cache_clear()
    engine = get_engine()
    yield engine
    await engine.dispose()
    get_engine.cache_clear()
    get_sessionmaker.cache_clear()


@pytest.fixture
async def db_session(engine: AsyncEngine) -> AsyncIterator[AsyncSession]:
    """Session as the API role, inside a transaction that is rolled back after the test."""
    async with engine.connect() as connection:
        transaction = await connection.begin()
        async with AsyncSession(
            bind=connection, join_transaction_mode="create_savepoint", expire_on_commit=False
        ) as session:
            yield session
        await transaction.rollback()


@pytest.fixture(scope="session")
async def redis_client(settings: Settings) -> AsyncIterator[Redis]:
    get_redis.cache_clear()
    client = get_redis()
    yield client
    await client.aclose()
    get_redis.cache_clear()


@pytest.fixture
async def redis(redis_client: Redis, settings: Settings) -> AsyncIterator[Redis]:
    """The app's Redis client; keys written under the test prefix are removed afterwards."""
    yield redis_client
    keys = [key async for key in redis_client.scan_iter(match=f"{settings.redis_key_prefix}*")]
    if keys:
        await redis_client.delete(*keys)


@pytest.fixture
def app(db_session: AsyncSession, redis: Redis) -> FastAPI:
    """The real app, with its database session bound to the test's rolled-back transaction."""
    from api.main import create_app

    async def session_override() -> AsyncIterator[AsyncSession]:
        yield db_session

    app = create_app()
    app.dependency_overrides[get_session] = session_override
    return app


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client


@pytest.fixture
def log_lines() -> Iterator[Callable[[], list[dict[str, Any]]]]:
    """Returns a function giving the JSON log lines written since the test began."""
    configure_logging()
    stream = io.StringIO()
    handler = build_handler(stream)
    root = logging.getLogger()
    root.addHandler(handler)

    def read() -> list[dict[str, Any]]:
        return [json.loads(line) for line in stream.getvalue().splitlines()]

    yield read
    root.removeHandler(handler)
