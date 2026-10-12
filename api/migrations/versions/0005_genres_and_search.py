"""FR-RD-01, FR-RD-06: the fixed genres, and what search needs

Revision ID: 0005
Revises: 0004

Genres are the tags with kind = 'genre': a fixed list the catalogue filters
on. They are inserted here rather than by the seed script, because every
environment needs them. The client translates their names by slug; the name
column holds the English one.

Search matches a substring of a work's title, its author's name or a tag,
after both sides went through core.search_normalize: NFC, diacritics removed,
lower case. "kiem si" and "Kiếm sĩ" therefore both find "Kiếm sĩ dưới trăng".
It is substring matching on trigrams, not a tsvector: Postgres full-text
splits on whitespace, which finds no words in Japanese and few in Korean,
while trigrams work for every content language.

unaccent() is only STABLE, because its dictionary could change, so it cannot
be indexed directly. The wrapper names the dictionary and is declared
IMMUTABLE; the three trigram indexes are on that expression. The indexes are
not in the models: Alembic's comparison of expression indexes is not
reliable, so autogenerate is told to leave indexes ending in _trgm alone.

Functions are executable by everyone by default, which covers app_rw.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from api.core.ids import uuid7

revision: str = "0005"
down_revision: str | Sequence[str] | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

GENRES = (
    ("action", "Action"),
    ("adventure", "Adventure"),
    ("comedy", "Comedy"),
    ("drama", "Drama"),
    ("fantasy", "Fantasy"),
    ("historical", "Historical"),
    ("horror", "Horror"),
    ("mystery", "Mystery"),
    ("romance", "Romance"),
    ("sci-fi", "Sci-Fi"),
    ("slice-of-life", "Slice of Life"),
    ("thriller", "Thriller"),
)

SEARCH_INDEXES = (
    ("ix_works_title_trgm", "works", "title"),
    ("ix_users_display_name_trgm", "users", "display_name"),
    ("ix_tags_name_trgm", "tags", "name"),
)


def upgrade() -> None:
    op.bulk_insert(
        sa.table(
            "tags",
            sa.column("id", sa.Uuid()),
            sa.column("slug", sa.Text()),
            sa.column("name", sa.Text()),
            sa.column("kind", sa.Text()),
            schema="core",
        ),
        [{"id": uuid7(), "slug": slug, "name": name, "kind": "genre"} for slug, name in GENRES],
    )

    op.execute(
        """
        CREATE FUNCTION core.search_normalize(value text) RETURNS text
            LANGUAGE sql IMMUTABLE STRICT PARALLEL SAFE
            AS $$ SELECT lower(public.unaccent('public.unaccent', normalize(value, NFC))) $$
        """
    )
    for name, table, column in SEARCH_INDEXES:
        op.execute(
            f"CREATE INDEX {name} ON core.{table}"
            f" USING gin (core.search_normalize({column}) public.gin_trgm_ops)"
        )


def downgrade() -> None:
    for name, _, _ in reversed(SEARCH_INDEXES):
        op.execute(f"DROP INDEX core.{name}")
    op.execute("DROP FUNCTION core.search_normalize(text)")
    # Takes the genre links of every work with it (work_tags cascades).
    op.execute("DELETE FROM core.tags WHERE kind = 'genre'")
