"""FR-AUTH-01, FR-AUTH-03: users, their roles and refresh tokens

Revision ID: 0002
Revises: 0001

core.users holds every piece of personal data about an account, so deleting an
account (FR-AUTH-05, built in Phase 3) is one row. user_roles and
refresh_tokens reference it with ON DELETE CASCADE: neither means anything
without the account.

Roles, status and locale are text with a CHECK rather than Postgres enums, so
adding a value later is an ordinary constraint change.

app_rw gets only what the code uses: it never deletes users or refresh tokens
(tokens are revoked, not removed) and never updates a role row.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | Sequence[str] | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("email", sa.Text(), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("display_name", sa.Text(), nullable=False),
        sa.Column("locale", sa.Text(), server_default="en", nullable=False),
        sa.Column("status", sa.Text(), server_default="active", nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("locale IN ('en', 'vi')", name=op.f("ck_users_locale")),
        sa.CheckConstraint("status IN ('active', 'locked')", name=op.f("ck_users_status")),
        sa.CheckConstraint("email = lower(email)", name=op.f("ck_users_email_lowercase")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.UniqueConstraint("email", name=op.f("uq_users_email")),
        schema="core",
    )
    op.create_table(
        "refresh_tokens",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("family_id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.Text(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["core.users.id"],
            name=op.f("fk_refresh_tokens_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_refresh_tokens")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_refresh_tokens_token_hash")),
        schema="core",
    )
    op.create_index(
        op.f("ix_refresh_tokens_family_id"),
        "refresh_tokens",
        ["family_id"],
        unique=False,
        schema="core",
    )
    op.create_index(
        op.f("ix_refresh_tokens_user_id"),
        "refresh_tokens",
        ["user_id"],
        unique=False,
        schema="core",
    )
    op.create_table(
        "user_roles",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "role IN ('reader', 'author', 'admin')", name=op.f("ck_user_roles_role")
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["core.users.id"],
            name=op.f("fk_user_roles_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_user_roles")),
        sa.UniqueConstraint("user_id", "role", name=op.f("uq_user_roles_user_id_role")),
        schema="core",
    )

    op.execute("GRANT SELECT, INSERT, UPDATE ON core.users TO app_rw")
    op.execute("GRANT SELECT, INSERT, DELETE ON core.user_roles TO app_rw")
    op.execute("GRANT SELECT, INSERT, UPDATE ON core.refresh_tokens TO app_rw")


def downgrade() -> None:
    op.drop_table("user_roles", schema="core")
    op.drop_index(op.f("ix_refresh_tokens_user_id"), table_name="refresh_tokens", schema="core")
    op.drop_index(op.f("ix_refresh_tokens_family_id"), table_name="refresh_tokens", schema="core")
    op.drop_table("refresh_tokens", schema="core")
    op.drop_table("users", schema="core")
