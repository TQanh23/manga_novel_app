import asyncio

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine

# Every module's models are imported here so autogenerate sees their tables.
import api.auth.models
import api.core.jobs  # noqa: F401
from api.core.config import get_settings
from api.core.logging import configure_logging
from api.core.models import Base

config = context.config

# Same JSON lines as the API, so the migrate container's output parses the same way.
configure_logging(get_settings().log_level)

target_metadata = Base.metadata

APP_SCHEMAS = frozenset({"core", "billing", "ai", "analytics"})


def include_name(name: str | None, type_: str, parent_names: object) -> bool:
    # Autogenerate only manages the app schemas; public holds extensions and alembic_version.
    if type_ == "schema":
        return name in APP_SCHEMAS
    return True


def database_url() -> str:
    # Tests point a run at another database through config.attributes.
    override = config.attributes.get("database_url")
    return str(override) if override else get_settings().migration_database_url


def run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        include_schemas=True,
        include_name=include_name,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    engine = create_async_engine(database_url(), poolclass=pool.NullPool)
    async with engine.connect() as connection:
        await connection.run_sync(run_migrations)
    await engine.dispose()


if context.is_offline_mode():
    # Migration 0001 reads a password from settings at run time, so SQL scripts
    # cannot be generated ahead of time.
    raise RuntimeError("Offline mode is not supported; run against a database.")

asyncio.run(run_async_migrations())
