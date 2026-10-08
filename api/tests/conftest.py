import os
from collections.abc import AsyncIterator, Callable, Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import make_url
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from api.core.config import Settings, get_settings
from api.core.db import get_engine, get_sessionmaker

API_DIR = Path(__file__).resolve().parents[1]
POSTGRES_IMAGE = "pgvector/pgvector:pg16"


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
def settings(owner_database_url: str) -> Iterator[Settings]:
    """Point the app at the test database, connecting as app_rw like the real API."""
    # Roles are cluster-wide: keep the configured password so that running the
    # tests against the Compose Postgres does not lock the dev stack out.
    password = Settings().app_rw_password.get_secret_value()
    app_url = make_url(owner_database_url).set(username="app_rw", password=password)

    with pytest.MonkeyPatch.context() as patch:
        patch.setenv("MIGRATION_DATABASE_URL", owner_database_url)
        patch.setenv("DATABASE_URL", app_url.render_as_string(hide_password=False))
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
