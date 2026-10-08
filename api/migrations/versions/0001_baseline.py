"""Baseline: extensions, schemas and the application roles

Revision ID: 0001
Revises:

app_rw is the role the API and worker connect as. It is not a superuser, owns
nothing and cannot create objects, which is what makes FORCE ROW LEVEL SECURITY
on later tables binding. Here it only gets USAGE on the schemas: there are no
default privileges, so every later migration grants table privileges explicitly.

app_public is a NOLOGIN role for shared features (recommendations, search,
tagging) that may only read published content. It gets USAGE on core and ai.

Roles belong to the cluster, not the database, so creation is guarded and
downgrade leaves a role in place while another database still grants it
something.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from api.core.config import get_settings

revision: str = "0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

EXTENSIONS = ("vector", "pg_trgm", "unaccent")
SCHEMAS = ("core", "billing", "ai", "analytics")


def upgrade() -> None:
    for extension in EXTENSIONS:
        op.execute(f"CREATE EXTENSION IF NOT EXISTS {extension}")
    for schema in SCHEMAS:
        op.execute(f"CREATE SCHEMA {schema}")

    # DDL takes no bind parameters, so the password reaches the DO block through
    # a transaction-local setting and is quoted there with format('%L').
    op.get_bind().execute(
        sa.text("SELECT set_config('migration.app_rw_password', :password, true)"),
        {"password": get_settings().app_rw_password.get_secret_value()},
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'app_rw') THEN
                CREATE ROLE app_rw;
            END IF;
            EXECUTE format(
                'ALTER ROLE app_rw WITH LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE'
                ' NOREPLICATION NOBYPASSRLS PASSWORD %L',
                current_setting('migration.app_rw_password')
            );
            IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'app_public') THEN
                CREATE ROLE app_public NOLOGIN;
            END IF;
        END
        $$
        """
    )

    op.execute("GRANT USAGE ON SCHEMA core, billing, ai, analytics TO app_rw")
    op.execute("GRANT USAGE ON SCHEMA core, ai TO app_public")


def downgrade() -> None:
    # No CASCADE: later migrations must have dropped their own tables first.
    for schema in reversed(SCHEMAS):
        op.execute(f"DROP SCHEMA {schema}")

    op.execute(
        """
        DO $$
        DECLARE
            role_name text;
        BEGIN
            FOREACH role_name IN ARRAY ARRAY['app_public', 'app_rw'] LOOP
                BEGIN
                    EXECUTE format('DROP ROLE IF EXISTS %I', role_name);
                EXCEPTION WHEN dependent_objects_still_exist THEN
                    RAISE NOTICE 'role % is still used by another database, left in place',
                        role_name;
                END;
            END LOOP;
        END
        $$
        """
    )

    for extension in reversed(EXTENSIONS):
        op.execute(f"DROP EXTENSION IF EXISTS {extension}")
