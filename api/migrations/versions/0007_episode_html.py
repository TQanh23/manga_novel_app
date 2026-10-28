"""FR-NV-01, FR-RD-03: an episode's text is HTML, not Markdown

Revision ID: 0007
Revises: 0006

Authors write in a rich-text editor and episode_versions.body_md becomes
body_html. The API stores only HTML it has sanitized (api/catalogue/text.py):
an allowlist of tags with no attributes, one top-level block per line.

Existing versions are converted here: each Markdown paragraph (text between
blank lines) is escaped and wrapped in <p>, and a single line break inside it
becomes <br>. Markdown syntax is not interpreted; the only text stored so far
is development data and the seed, which uses none. The conversion is written
out here rather than imported, so later changes to the sanitizer cannot change
what this migration did.

The table forces row-level security and its policies name app_rw only, so the
owner running this migration would update no rows. FORCE is lifted for the
update and restored in the same transaction.

Downgrade renames the column back and leaves the HTML in it: the Markdown is
not recovered.
"""

import re
from collections.abc import Sequence
from html import escape

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: str | Sequence[str] | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_BLANK_LINES = re.compile(r"(?:\r?\n[ \t]*){2,}")


def _markdown_to_html(body_md: str) -> str:
    paragraphs = (part.strip() for part in _BLANK_LINES.split(body_md))
    return "\n".join(
        "<p>" + escape(part, quote=False).replace("\r\n", "\n").replace("\n", "<br>") + "</p>"
        for part in paragraphs
        if part
    )


def upgrade() -> None:
    op.alter_column("episode_versions", "body_md", new_column_name="body_html", schema="core")

    connection = op.get_bind()
    op.execute("ALTER TABLE core.episode_versions NO FORCE ROW LEVEL SECURITY")
    rows = connection.execute(sa.text("SELECT id, body_html FROM core.episode_versions")).all()
    for version_id, body in rows:
        connection.execute(
            sa.text("UPDATE core.episode_versions SET body_html = :body WHERE id = :id"),
            {"body": _markdown_to_html(body), "id": version_id},
        )
    op.execute("ALTER TABLE core.episode_versions FORCE ROW LEVEL SECURITY")


def downgrade() -> None:
    op.alter_column("episode_versions", "body_html", new_column_name="body_md", schema="core")
