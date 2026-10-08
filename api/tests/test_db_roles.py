"""The API's database role must stay unprivileged.

Row-level security (NFR-06) does not apply to superusers, roles with BYPASSRLS
or, without FORCE, the table owner. These tests fail if the API ever connects
as one of those.
"""

import pytest
from sqlalchemy import text
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.ext.asyncio import AsyncSession

APP_SCHEMAS = ["core", "billing", "ai", "analytics"]


async def test_api_role_is_app_rw_without_elevated_attributes(db_session: AsyncSession) -> None:
    row = (
        await db_session.execute(
            text(
                "SELECT rolname, rolsuper, rolbypassrls, rolcreaterole, rolcreatedb, rolreplication"
                " FROM pg_roles WHERE rolname = current_user"
            )
        )
    ).one()

    assert row.rolname == "app_rw"
    assert not row.rolsuper
    assert not row.rolbypassrls
    assert not row.rolcreaterole
    assert not row.rolcreatedb
    assert not row.rolreplication


async def test_api_role_owns_nothing_in_app_schemas(db_session: AsyncSession) -> None:
    owned_schemas = (
        await db_session.execute(
            text(
                "SELECT nspname FROM pg_namespace"
                " WHERE nspname = ANY(:schemas) AND pg_get_userbyid(nspowner) = current_user"
            ),
            {"schemas": APP_SCHEMAS},
        )
    ).all()
    owned_relations = (
        await db_session.execute(
            text(
                "SELECT n.nspname, c.relname FROM pg_class c"
                " JOIN pg_namespace n ON n.oid = c.relnamespace"
                " WHERE n.nspname = ANY(:schemas) AND pg_get_userbyid(c.relowner) = current_user"
            ),
            {"schemas": APP_SCHEMAS},
        )
    ).all()

    assert owned_schemas == []
    assert owned_relations == []


@pytest.mark.parametrize("schema", [*APP_SCHEMAS, "public"])
async def test_api_role_cannot_create_tables(db_session: AsyncSession, schema: str) -> None:
    # A table the API role created would be owned by it, and owners can lift RLS.
    with pytest.raises(ProgrammingError, match="permission denied"):
        await db_session.execute(text(f"CREATE TABLE {schema}.owned_by_api (id int)"))


async def test_api_role_can_use_app_schemas(db_session: AsyncSession) -> None:
    usable = (
        await db_session.execute(
            text(
                "SELECT s FROM unnest(CAST(:schemas AS text[])) AS s"
                " WHERE has_schema_privilege(current_user, s, 'USAGE')"
            ),
            {"schemas": APP_SCHEMAS},
        )
    ).scalars()

    assert sorted(usable) == sorted(APP_SCHEMAS)
