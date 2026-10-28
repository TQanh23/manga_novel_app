import asyncio
from collections.abc import Callable, Iterator, Sequence
from typing import Any

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Row, make_url, text
from sqlalchemy.ext.asyncio import create_async_engine

from api.core.config import Settings
from api.core.ids import uuid7

SCRATCH_DATABASE = "migration_round_trip"
APP_SCHEMAS = ["ai", "analytics", "billing", "core"]
EXTENSIONS = ["pg_trgm", "unaccent", "vector"]


def run_sql(url: str, statement: str, params: dict[str, Any] | None = None) -> Sequence[Row[Any]]:
    async def run() -> Sequence[Row[Any]]:
        engine = create_async_engine(url, isolation_level="AUTOCOMMIT")
        try:
            async with engine.connect() as connection:
                result = await connection.execute(text(statement), params or {})
                return result.all() if result.returns_rows else []
        finally:
            await engine.dispose()

    return asyncio.run(run())


@pytest.fixture
def scratch_database_url(settings: Settings) -> Iterator[str]:
    """An empty database on the test server, so the round trip never touches the shared one."""
    owner_url = settings.migration_database_url
    run_sql(owner_url, f"DROP DATABASE IF EXISTS {SCRATCH_DATABASE} WITH (FORCE)")
    run_sql(owner_url, f"CREATE DATABASE {SCRATCH_DATABASE}")
    yield make_url(owner_url).set(database=SCRATCH_DATABASE).render_as_string(hide_password=False)
    run_sql(owner_url, f"DROP DATABASE {SCRATCH_DATABASE} WITH (FORCE)")


def app_schemas(url: str) -> list[str]:
    rows = run_sql(
        url,
        "SELECT nspname FROM pg_namespace WHERE nspname = ANY(:names) ORDER BY 1",
        {"names": APP_SCHEMAS},
    )
    return [row.nspname for row in rows]


def extensions(url: str) -> list[str]:
    rows = run_sql(
        url,
        "SELECT extname FROM pg_extension WHERE extname = ANY(:names) ORDER BY 1",
        {"names": EXTENSIONS},
    )
    return [row.extname for row in rows]


def test_migrations_round_trip(
    scratch_database_url: str, alembic_config: Callable[..., Config]
) -> None:
    config = alembic_config(scratch_database_url)

    command.upgrade(config, "head")
    assert app_schemas(scratch_database_url) == APP_SCHEMAS
    assert extensions(scratch_database_url) == EXTENSIONS

    command.downgrade(config, "base")
    assert app_schemas(scratch_database_url) == []
    assert extensions(scratch_database_url) == []
    assert run_sql(scratch_database_url, "SELECT version_num FROM alembic_version") == []

    command.upgrade(config, "head")
    assert app_schemas(scratch_database_url) == APP_SCHEMAS
    roles = run_sql(
        scratch_database_url,
        "SELECT rolname, rolcanlogin FROM pg_roles"
        " WHERE rolname IN ('app_rw', 'app_public') ORDER BY 1",
    )
    assert [tuple(row) for row in roles] == [("app_public", False), ("app_rw", True)]


def test_0007_turns_stored_markdown_paragraphs_into_html(
    scratch_database_url: str, alembic_config: Callable[..., Config]
) -> None:
    config = alembic_config(scratch_database_url)
    command.upgrade(config, "0006")
    ids = {name: str(uuid7()) for name in ("user", "work", "episode", "version")}
    for statement in (
        "INSERT INTO core.users (id, email, password_hash, display_name)"
        " VALUES (CAST(:user AS uuid), 'a@example.com', 'x', 'A')",
        "INSERT INTO core.works (id, author_id, type, title, language)"
        " VALUES (CAST(:work AS uuid), CAST(:user AS uuid), 'novel', 'W', 'vi')",
        "INSERT INTO core.episodes (id, work_id, author_id, number, title)"
        " VALUES (CAST(:episode AS uuid), CAST(:work AS uuid), CAST(:user AS uuid), 1, 'E')",
        "INSERT INTO core.episode_versions (id, episode_id, author_id, body_md)"
        " VALUES (CAST(:version AS uuid), CAST(:episode AS uuid), CAST(:user AS uuid), :body)",
    ):
        run_sql(
            scratch_database_url,
            statement,
            {**ids, "body": "# Đầu\n\nMột <b>&</b> hai\ndòng ba\n\n\n月の下で"},
        )

    command.upgrade(config, "0007")

    # The table forces row-level security; the update must still have reached the row.
    rows = run_sql(scratch_database_url, "SELECT body_html FROM core.episode_versions")
    assert [row.body_html for row in rows] == [
        "<p># Đầu</p>\n<p>Một &lt;b&gt;&amp;&lt;/b&gt; hai<br>dòng ba</p>\n<p>月の下で</p>"
    ]
    forced = run_sql(
        scratch_database_url,
        "SELECT relforcerowsecurity FROM pg_class WHERE oid = 'core.episode_versions'::regclass",
    )
    assert forced[0].relforcerowsecurity is True
