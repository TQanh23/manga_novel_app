from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    Text,
    UniqueConstraint,
    false,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from api.core.models import Base, TimestampMixin, UUIDPrimaryKeyMixin, one_of


class WorkType(StrEnum):
    NOVEL = "novel"
    MANGA = "manga"


class ContentLanguage(StrEnum):
    KO = "ko"
    JA = "ja"
    EN = "en"
    VI = "vi"


class WorkStatus(StrEnum):
    ONGOING = "ongoing"
    COMPLETED = "completed"


class EpisodeStatus(StrEnum):
    DRAFT = "draft"
    SCHEDULED = "scheduled"
    PUBLISHED = "published"
    REMOVED = "removed"


class TagKind(StrEnum):
    # Genres are a fixed list the catalogue filters on; the client translates
    # their names by slug. Plain tags are whatever an author typed.
    GENRE = "genre"
    TAG = "tag"


class TagSource(StrEnum):
    AUTHOR = "author"
    AI_SUGGESTED_APPROVED = "ai_suggested_approved"


class GlossaryKind(StrEnum):
    CHARACTER = "character"
    PLACE = "place"
    TERM = "term"


class Work(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A novel or a manga, owned by one author."""

    __tablename__ = "works"
    __table_args__ = (
        # Target of the composite key episodes use to carry the same author_id.
        UniqueConstraint("id", "author_id"),
        CheckConstraint(one_of("type", WorkType), name="type"),
        CheckConstraint(one_of("language", ContentLanguage), name="language"),
        CheckConstraint(one_of("status", WorkStatus), name="status"),
        {"schema": "core"},
    )

    author_id: Mapped[UUID] = mapped_column(
        ForeignKey("core.users.id", ondelete="RESTRICT"), index=True
    )
    type: Mapped[str] = mapped_column(Text)
    title: Mapped[str] = mapped_column(Text)
    synopsis: Mapped[str] = mapped_column(Text, default="", server_default="")
    language: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(
        Text, default=WorkStatus.ONGOING, server_default=WorkStatus.ONGOING
    )
    # The author picks the wait-until-free period, an admin assigns the split.
    # Nothing in the schema ties a column to a preset kind; the service checks it.
    wuf_preset_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("core.config_presets.id", ondelete="RESTRICT")
    )
    revenue_share_preset_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("core.config_presets.id", ondelete="RESTRICT")
    )
    # Written for this project, so it may go to providers that train on input.
    is_sample: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    # Off unless the author turns it on. Nothing that exports or fine-tunes
    # reads a work with this off.
    ai_opt_in_training: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())


class Episode(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One chapter of a work. Its text lives in episode_versions."""

    __tablename__ = "episodes"
    __table_args__ = (
        # Composite, so an episode cannot name an author other than its work's.
        ForeignKeyConstraint(
            ["work_id", "author_id"],
            ["core.works.id", "core.works.author_id"],
            ondelete="CASCADE",
        ),
        UniqueConstraint("work_id", "number"),
        UniqueConstraint("id", "author_id"),
        CheckConstraint(one_of("status", EpisodeStatus), name="status"),
        CheckConstraint("number > 0", name="number_positive"),
        CheckConstraint("price_coins >= 0", name="price_coins_not_negative"),
        CheckConstraint(
            "status NOT IN ('scheduled', 'published') OR publish_at IS NOT NULL",
            name="publish_at_set",
        ),
        # What the scheduled-publish cron scans every minute.
        Index(
            "ix_episodes_scheduled_publish_at",
            "publish_at",
            postgresql_where=text("status = 'scheduled'"),
        ),
        {"schema": "core"},
    )

    work_id: Mapped[UUID]
    author_id: Mapped[UUID]
    number: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(
        Text, default=EpisodeStatus.DRAFT, server_default=EpisodeStatus.DRAFT
    )
    # When a scheduled episode goes live, then when it went live.
    publish_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    price_coins: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    wuf_eligible: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    # The version readers see. NO ACTION: the published version cannot be
    # deleted on its own, but goes with the episode when that is deleted.
    published_version_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("core.episode_versions.id", ondelete="NO ACTION", use_alter=True), unique=True
    )


class EpisodeVersion(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One save of an episode's text. Rows are never updated.

    Drafts are author-private: the table is under row-level security keyed on
    author_id, and the composite key makes that column the work's real author.
    """

    __tablename__ = "episode_versions"
    __table_args__ = (
        ForeignKeyConstraint(
            ["episode_id", "author_id"],
            ["core.episodes.id", "core.episodes.author_id"],
            ondelete="CASCADE",
        ),
        {"schema": "core"},
    )

    episode_id: Mapped[UUID] = mapped_column(index=True)
    author_id: Mapped[UUID]
    body_html: Mapped[str] = mapped_column(Text)
    created_by: Mapped[UUID | None] = mapped_column(
        ForeignKey("core.users.id", ondelete="SET NULL")
    )


class Tag(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "tags"
    __table_args__ = (
        UniqueConstraint("slug"),
        CheckConstraint("slug = lower(slug)", name="slug_lowercase"),
        CheckConstraint(one_of("kind", TagKind), name="kind"),
        {"schema": "core"},
    )

    slug: Mapped[str] = mapped_column(Text)
    name: Mapped[str] = mapped_column(Text)
    kind: Mapped[str] = mapped_column(Text, default=TagKind.TAG, server_default=TagKind.TAG)


class WorkTag(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "work_tags"
    __table_args__ = (
        UniqueConstraint("work_id", "tag_id"),
        CheckConstraint(one_of("source", TagSource), name="source"),
        {"schema": "core"},
    )

    work_id: Mapped[UUID] = mapped_column(ForeignKey("core.works.id", ondelete="CASCADE"))
    tag_id: Mapped[UUID] = mapped_column(ForeignKey("core.tags.id", ondelete="CASCADE"), index=True)
    source: Mapped[str] = mapped_column(
        Text, default=TagSource.AUTHOR, server_default=TagSource.AUTHOR
    )


class GlossaryEntry(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A character, place or term of a work, with what is known about it (FR-NV-03)."""

    __tablename__ = "glossary_entries"
    __table_args__ = (
        UniqueConstraint("work_id", "kind", "name"),
        CheckConstraint(one_of("kind", GlossaryKind), name="kind"),
        {"schema": "core"},
    )

    work_id: Mapped[UUID] = mapped_column(ForeignKey("core.works.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(Text)
    name: Mapped[str] = mapped_column(Text)
    aliases: Mapped[list[str]] = mapped_column(
        ARRAY(Text), default=list, server_default=text("'{}'")
    )
    # Free-form facts the consistency check compares against: eye colour, age, relations.
    attributes: Mapped[dict[str, Any]] = mapped_column(
        JSONB, default=dict, server_default=text("'{}'")
    )
    # The name in other languages, keyed by language code.
    translations: Mapped[dict[str, Any]] = mapped_column(
        JSONB, default=dict, server_default=text("'{}'")
    )
