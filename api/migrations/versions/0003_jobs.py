"""Background jobs: one row per (kind, target_id, content_hash)

Revision ID: 0003
Revises: 0002

core.jobs is the idempotency record and the status of every piece of worker
work. The unique key means the same work on the same input is one job. Rows
hold metadata only (ids, a hash, a status, an error class name), never content.

target_id has no foreign key: it points at whatever the job works on, which
differs by kind. Cleaning up the jobs of a deleted work belongs to the delete
path, added with the first job that targets a work (Phase 2).

app_rw may not delete jobs; nothing in the code does.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | Sequence[str] | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "jobs",
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("target_id", sa.Uuid(), nullable=False),
        sa.Column("content_hash", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), server_default="queued", nullable=False),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("request_id", sa.Text(), nullable=True),
        sa.Column("error_code", sa.Text(), nullable=True),
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
            "status IN ('queued', 'running', 'succeeded', 'failed')", name=op.f("ck_jobs_status")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_jobs")),
        sa.UniqueConstraint(
            "kind", "target_id", "content_hash", name=op.f("uq_jobs_kind_target_id_content_hash")
        ),
        schema="core",
    )

    op.execute("GRANT SELECT, INSERT, UPDATE ON core.jobs TO app_rw")


def downgrade() -> None:
    op.drop_table("jobs", schema="core")
