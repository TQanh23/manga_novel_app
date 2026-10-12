"""FR-NV-01, FR-NV-03, FR-RD-05, FR-AD-04: works, episodes, drafts, tags, glossary, presets

Revision ID: 0004
Revises: 0003

The content model every later phase builds on, all in core.

What a delete takes with it:

- works.author_id is RESTRICT. What happens to an author's works when the
  account goes is undecided, so until then an author with works cannot be
  deleted by accident.
- Everything that belongs to a work goes with it (CASCADE): episodes,
  episode_versions, work_tags, glossary_entries and, through episodes,
  reading_progress. Deleting the works row is the whole of the hard delete in
  Postgres. A later table that references a work or an episode cascades too.
- episodes.published_version_id is NO ACTION: the version readers see cannot
  be deleted on its own, but goes with its episode.
- works.*_preset_id are RESTRICT: a preset is retired with active = false,
  never deleted, because unlocks will snapshot it.
- episode_versions.created_by is SET NULL: the version stays the author's.
- reading_progress.user_id and work_tags.tag_id are CASCADE: the row means
  nothing without the reader or the tag.

episodes and episode_versions repeat the work's author_id, and composite
foreign keys keep the copies equal to works.author_id. That is what lets the
row-level security policy on episode_versions trust the column: drafts are
visible to their author only, whatever query the application runs. Everyone
may read the one version an episode has published. Episode rows themselves are
not under RLS; they hold no manuscript text.

The WUF periods and revenue splits are inserted here rather than by the seed
script, because every environment needs them and the seed only runs locally.

app_rw gets what the Phase 1 code uses. It cannot delete works, episodes or
versions (the hard delete grants that when it is built), cannot rewrite a
saved version, and can only read presets.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from api.core.ids import uuid7

revision: str = "0004"
down_revision: str | Sequence[str] | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# wuf_period is in seconds: 3 hours, 12 hours, 1 day, 3 days.
# revenue_share is the author's percent; the platform keeps the rest.
PRESETS = {
    "wuf_period": (10_800, 43_200, 86_400, 259_200),
    "revenue_share": (50, 60, 70),
}

CURRENT_AUTHOR = "NULLIF(current_setting('app.author_id', true), '')::uuid"


def upgrade() -> None:
    op.create_table(
        "config_presets",
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("value", sa.Integer(), nullable=False),
        sa.Column("active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
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
            "kind <> 'revenue_share' OR value <= 100",
            name=op.f("ck_config_presets_revenue_share_percent"),
        ),
        sa.CheckConstraint(
            "kind IN ('wuf_period', 'revenue_share')", name=op.f("ck_config_presets_kind")
        ),
        sa.CheckConstraint("value > 0", name=op.f("ck_config_presets_value_positive")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_config_presets")),
        sa.UniqueConstraint("kind", "value", name=op.f("uq_config_presets_kind_value")),
        schema="core",
    )
    op.create_table(
        "tags",
        sa.Column("slug", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("kind", sa.Text(), server_default="tag", nullable=False),
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
        sa.CheckConstraint("kind IN ('genre', 'tag')", name=op.f("ck_tags_kind")),
        sa.CheckConstraint("slug = lower(slug)", name=op.f("ck_tags_slug_lowercase")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tags")),
        sa.UniqueConstraint("slug", name=op.f("uq_tags_slug")),
        schema="core",
    )
    op.create_table(
        "works",
        sa.Column("author_id", sa.Uuid(), nullable=False),
        sa.Column("type", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("synopsis", sa.Text(), server_default="", nullable=False),
        sa.Column("language", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), server_default="ongoing", nullable=False),
        sa.Column("wuf_preset_id", sa.Uuid(), nullable=True),
        sa.Column("revenue_share_preset_id", sa.Uuid(), nullable=True),
        sa.Column("is_sample", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column(
            "ai_opt_in_training", sa.Boolean(), server_default=sa.text("false"), nullable=False
        ),
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
        sa.CheckConstraint("language IN ('ko', 'ja', 'en', 'vi')", name=op.f("ck_works_language")),
        sa.CheckConstraint("status IN ('ongoing', 'completed')", name=op.f("ck_works_status")),
        sa.CheckConstraint("type IN ('novel', 'manga')", name=op.f("ck_works_type")),
        sa.ForeignKeyConstraint(
            ["author_id"],
            ["core.users.id"],
            name=op.f("fk_works_author_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["revenue_share_preset_id"],
            ["core.config_presets.id"],
            name=op.f("fk_works_revenue_share_preset_id_config_presets"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["wuf_preset_id"],
            ["core.config_presets.id"],
            name=op.f("fk_works_wuf_preset_id_config_presets"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_works")),
        sa.UniqueConstraint("id", "author_id", name=op.f("uq_works_id_author_id")),
        schema="core",
    )
    op.create_index(op.f("ix_works_author_id"), "works", ["author_id"], unique=False, schema="core")
    op.create_table(
        "episodes",
        sa.Column("work_id", sa.Uuid(), nullable=False),
        sa.Column("author_id", sa.Uuid(), nullable=False),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), server_default="draft", nullable=False),
        sa.Column("publish_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("price_coins", sa.Integer(), server_default="0", nullable=False),
        sa.Column("wuf_eligible", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("published_version_id", sa.Uuid(), nullable=True),
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
            "status IN ('draft', 'scheduled', 'published', 'removed')",
            name=op.f("ck_episodes_status"),
        ),
        sa.CheckConstraint(
            "status NOT IN ('scheduled', 'published') OR publish_at IS NOT NULL",
            name=op.f("ck_episodes_publish_at_set"),
        ),
        sa.CheckConstraint("number > 0", name=op.f("ck_episodes_number_positive")),
        sa.CheckConstraint("price_coins >= 0", name=op.f("ck_episodes_price_coins_not_negative")),
        sa.ForeignKeyConstraint(
            ["work_id", "author_id"],
            ["core.works.id", "core.works.author_id"],
            name=op.f("fk_episodes_work_id_works"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_episodes")),
        sa.UniqueConstraint("id", "author_id", name=op.f("uq_episodes_id_author_id")),
        sa.UniqueConstraint("published_version_id", name=op.f("uq_episodes_published_version_id")),
        sa.UniqueConstraint("work_id", "number", name=op.f("uq_episodes_work_id_number")),
        schema="core",
    )
    op.create_index(
        "ix_episodes_scheduled_publish_at",
        "episodes",
        ["publish_at"],
        unique=False,
        schema="core",
        postgresql_where=sa.text("status = 'scheduled'"),
    )
    op.create_table(
        "glossary_entries",
        sa.Column("work_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column(
            "aliases", postgresql.ARRAY(sa.Text()), server_default=sa.text("'{}'"), nullable=False
        ),
        sa.Column(
            "attributes",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'"),
            nullable=False,
        ),
        sa.Column(
            "translations",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'"),
            nullable=False,
        ),
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
            "kind IN ('character', 'place', 'term')", name=op.f("ck_glossary_entries_kind")
        ),
        sa.ForeignKeyConstraint(
            ["work_id"],
            ["core.works.id"],
            name=op.f("fk_glossary_entries_work_id_works"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_glossary_entries")),
        sa.UniqueConstraint(
            "work_id", "kind", "name", name=op.f("uq_glossary_entries_work_id_kind_name")
        ),
        schema="core",
    )
    op.create_table(
        "work_tags",
        sa.Column("work_id", sa.Uuid(), nullable=False),
        sa.Column("tag_id", sa.Uuid(), nullable=False),
        sa.Column("source", sa.Text(), server_default="author", nullable=False),
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
            "source IN ('author', 'ai_suggested_approved')", name=op.f("ck_work_tags_source")
        ),
        sa.ForeignKeyConstraint(
            ["tag_id"], ["core.tags.id"], name=op.f("fk_work_tags_tag_id_tags"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["work_id"],
            ["core.works.id"],
            name=op.f("fk_work_tags_work_id_works"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_work_tags")),
        sa.UniqueConstraint("work_id", "tag_id", name=op.f("uq_work_tags_work_id_tag_id")),
        schema="core",
    )
    op.create_index(
        op.f("ix_work_tags_tag_id"), "work_tags", ["tag_id"], unique=False, schema="core"
    )
    op.create_table(
        "episode_versions",
        sa.Column("episode_id", sa.Uuid(), nullable=False),
        sa.Column("author_id", sa.Uuid(), nullable=False),
        sa.Column("body_md", sa.Text(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
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
            ["created_by"],
            ["core.users.id"],
            name=op.f("fk_episode_versions_created_by_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["episode_id", "author_id"],
            ["core.episodes.id", "core.episodes.author_id"],
            name=op.f("fk_episode_versions_episode_id_episodes"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_episode_versions")),
        schema="core",
    )
    op.create_index(
        op.f("ix_episode_versions_episode_id"),
        "episode_versions",
        ["episode_id"],
        unique=False,
        schema="core",
    )
    # episodes and episode_versions point at each other, so this half waits
    # until both exist.
    op.create_foreign_key(
        op.f("fk_episodes_published_version_id_episode_versions"),
        "episodes",
        "episode_versions",
        ["published_version_id"],
        ["id"],
        source_schema="core",
        referent_schema="core",
        ondelete="NO ACTION",
    )
    op.create_table(
        "reading_progress",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("episode_id", sa.Uuid(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
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
        sa.CheckConstraint("position >= 0", name=op.f("ck_reading_progress_position_not_negative")),
        sa.ForeignKeyConstraint(
            ["episode_id"],
            ["core.episodes.id"],
            name=op.f("fk_reading_progress_episode_id_episodes"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["core.users.id"],
            name=op.f("fk_reading_progress_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_reading_progress")),
        sa.UniqueConstraint(
            "user_id", "episode_id", name=op.f("uq_reading_progress_user_id_episode_id")
        ),
        schema="core",
    )
    op.create_index(
        op.f("ix_reading_progress_episode_id"),
        "reading_progress",
        ["episode_id"],
        unique=False,
        schema="core",
    )

    op.bulk_insert(
        sa.table(
            "config_presets",
            sa.column("id", sa.Uuid()),
            sa.column("kind", sa.Text()),
            sa.column("value", sa.Integer()),
            schema="core",
        ),
        [
            {"id": uuid7(), "kind": kind, "value": value}
            for kind, values in PRESETS.items()
            for value in values
        ],
    )

    # FORCE: without it the table owner would bypass the policies.
    op.execute("ALTER TABLE core.episode_versions ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE core.episode_versions FORCE ROW LEVEL SECURITY")
    # A transaction that has not named an author matches no row: the setting
    # is NULL when never set and '' once a transaction that set it has ended.
    op.execute(
        f"""
        CREATE POLICY author_isolation ON core.episode_versions TO app_rw
            USING (author_id = {CURRENT_AUTHOR})
            WITH CHECK (author_id = {CURRENT_AUTHOR})
        """
    )
    op.execute(
        """
        CREATE POLICY published_read ON core.episode_versions FOR SELECT TO app_rw
            USING (
                EXISTS (
                    SELECT 1 FROM core.episodes e
                    WHERE e.published_version_id = episode_versions.id
                        AND e.status = 'published'
                )
            )
        """
    )

    op.execute("GRANT SELECT ON core.config_presets TO app_rw")
    op.execute("GRANT SELECT, INSERT, UPDATE ON core.works TO app_rw")
    op.execute("GRANT SELECT, INSERT, UPDATE ON core.episodes TO app_rw")
    op.execute("GRANT SELECT, INSERT ON core.episode_versions TO app_rw")
    op.execute("GRANT SELECT, INSERT ON core.tags TO app_rw")
    op.execute("GRANT SELECT, INSERT, DELETE ON core.work_tags TO app_rw")
    op.execute("GRANT SELECT, INSERT, UPDATE ON core.glossary_entries TO app_rw")
    op.execute("GRANT SELECT, INSERT, UPDATE ON core.reading_progress TO app_rw")


def downgrade() -> None:
    op.execute("DROP POLICY published_read ON core.episode_versions")
    op.execute("DROP POLICY author_isolation ON core.episode_versions")
    op.drop_constraint(
        op.f("fk_episodes_published_version_id_episode_versions"),
        "episodes",
        schema="core",
        type_="foreignkey",
    )
    op.drop_index(
        op.f("ix_reading_progress_episode_id"), table_name="reading_progress", schema="core"
    )
    op.drop_table("reading_progress", schema="core")
    op.drop_index(
        op.f("ix_episode_versions_episode_id"), table_name="episode_versions", schema="core"
    )
    op.drop_table("episode_versions", schema="core")
    op.drop_index(op.f("ix_work_tags_tag_id"), table_name="work_tags", schema="core")
    op.drop_table("work_tags", schema="core")
    op.drop_table("glossary_entries", schema="core")
    op.drop_index(
        "ix_episodes_scheduled_publish_at",
        table_name="episodes",
        schema="core",
        postgresql_where=sa.text("status = 'scheduled'"),
    )
    op.drop_table("episodes", schema="core")
    op.drop_index(op.f("ix_works_author_id"), table_name="works", schema="core")
    op.drop_table("works", schema="core")
    op.drop_table("tags", schema="core")
    op.drop_table("config_presets", schema="core")
