"""FR-NV-03: authors can delete a glossary entry

Revision ID: 0008
Revises: 0007

Closes the gap noted in 1.4: the spec lists GET, POST and PATCH for the
glossary, and 0004 gave app_rw no DELETE on core.glossary_entries. An author
who adds an entry by mistake, or drops a character from the story, must be
able to take it out, or the consistency check (Phase 4) would keep comparing
chapters with facts that no longer hold.

Nothing references a glossary entry, so deleting one removes that row alone.

Downgrade revokes the privilege again.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0008"
down_revision: str | Sequence[str] | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("GRANT DELETE ON core.glossary_entries TO app_rw")


def downgrade() -> None:
    op.execute("REVOKE DELETE ON core.glossary_entries FROM app_rw")
