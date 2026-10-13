from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from api.core.models import Base, TimestampMixin, UUIDPrimaryKeyMixin


class ReadingProgress(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Where one reader stopped in one episode, shared by all their devices (FR-RD-05)."""

    __tablename__ = "reading_progress"
    __table_args__ = (
        UniqueConstraint("user_id", "episode_id"),
        CheckConstraint("position >= 0", name="position_not_negative"),
        {"schema": "core"},
    )

    user_id: Mapped[UUID] = mapped_column(ForeignKey("core.users.id", ondelete="CASCADE"))
    episode_id: Mapped[UUID] = mapped_column(
        ForeignKey("core.episodes.id", ondelete="CASCADE"), index=True
    )
    # Paragraph index in a novel, tile index in a manga.
    position: Mapped[int] = mapped_column(Integer)


class Favourite(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A work a reader keeps in their library (FR-RD-05)."""

    __tablename__ = "favourites"
    __table_args__ = (UniqueConstraint("user_id", "work_id"), {"schema": "core"})

    user_id: Mapped[UUID] = mapped_column(ForeignKey("core.users.id", ondelete="CASCADE"))
    work_id: Mapped[UUID] = mapped_column(
        ForeignKey("core.works.id", ondelete="CASCADE"), index=True
    )
