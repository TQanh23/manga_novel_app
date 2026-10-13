"""FR-RD-05: the works a reader keeps in their library

Revision ID: 0006
Revises: 0005

One row per (reader, work). Both foreign keys are CASCADE: a favourite means
nothing without the reader, and it goes with the work when that is deleted,
like everything else that references a work.

Favourites and reading progress are a reader's own data but hold no manuscript
text, so they are not under row-level security; every query filters on
user_id.

app_rw adds and removes favourites and never rewrites one.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: str | Sequence[str] | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "favourites",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("work_id", sa.Uuid(), nullable=False),
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
            name=op.f("fk_favourites_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["work_id"],
            ["core.works.id"],
            name=op.f("fk_favourites_work_id_works"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_favourites")),
        sa.UniqueConstraint("user_id", "work_id", name=op.f("uq_favourites_user_id_work_id")),
        schema="core",
    )
    op.create_index(
        op.f("ix_favourites_work_id"), "favourites", ["work_id"], unique=False, schema="core"
    )

    op.execute("GRANT SELECT, INSERT, DELETE ON core.favourites TO app_rw")


def downgrade() -> None:
    op.drop_index(op.f("ix_favourites_work_id"), table_name="favourites", schema="core")
    op.drop_table("favourites", schema="core")
