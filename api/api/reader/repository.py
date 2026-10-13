"""Queries behind reading: episode text, progress and the library.

An episode is read through `get_published_episode` only, so nothing here can
return a draft, a scheduled or a removed episode. A reader's progress and
favourites are always looked up with their user id.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import distinct_on, insert
from sqlalchemy.ext.asyncio import AsyncSession

from api.catalogue.models import Episode, EpisodeStatus, EpisodeVersion, Work
from api.core.ids import uuid7
from api.reader.models import Favourite, ReadingProgress

LIBRARY_LIMIT = 100


@dataclass(frozen=True)
class LastRead:
    """The episode of a work a reader was in most recently."""

    work_id: UUID
    episode_id: UUID
    episode_number: int
    episode_title: str
    position: int
    read_at: datetime


async def get_published_episode(
    session: AsyncSession, episode_id: UUID
) -> tuple[Episode, str] | None:
    """A published episode and the type of its work, or None."""
    statement = (
        select(Episode, Work.type)
        .join(Work, Work.id == Episode.work_id)
        .where(Episode.id == episode_id, Episode.status == EpisodeStatus.PUBLISHED)
        # The row as it is now, never a copy the session already holds: status
        # and price decide whether the text may be shown.
        .execution_options(populate_existing=True)
    )
    row = (await session.execute(statement)).one_or_none()
    return (row[0], row[1]) if row is not None else None


async def get_published_text(session: AsyncSession, version_id: UUID) -> str | None:
    # No author is named in a reader's transaction, so row-level security lets
    # this see a version only if an episode has published it.
    statement = select(EpisodeVersion.body_md).where(EpisodeVersion.id == version_id)
    return (await session.execute(statement)).scalar_one_or_none()


async def neighbours(session: AsyncSession, episode: Episode) -> tuple[UUID | None, UUID | None]:
    """The published episodes just before and just after this one in its work."""
    in_work = select(Episode.id).where(
        Episode.work_id == episode.work_id, Episode.status == EpisodeStatus.PUBLISHED
    )
    previous = in_work.where(Episode.number < episode.number).order_by(Episode.number.desc())
    following = in_work.where(Episode.number > episode.number).order_by(Episode.number)
    return (
        (await session.execute(previous.limit(1))).scalar_one_or_none(),
        (await session.execute(following.limit(1))).scalar_one_or_none(),
    )


async def get_position(session: AsyncSession, user_id: UUID, episode_id: UUID) -> int | None:
    statement = select(ReadingProgress.position).where(
        ReadingProgress.user_id == user_id, ReadingProgress.episode_id == episode_id
    )
    return (await session.execute(statement)).scalar_one_or_none()


async def save_position(
    session: AsyncSession, user_id: UUID, episode_id: UUID, position: int
) -> datetime:
    """Record where the reader is; returns when it was recorded.

    One statement: a reader's devices may write at the same moment, and the
    later write simply wins.
    """
    # The clock, not the transaction's start, so writes order by when they happened.
    now = func.clock_timestamp()
    statement = (
        insert(ReadingProgress)
        .values(
            id=uuid7(), user_id=user_id, episode_id=episode_id, position=position, updated_at=now
        )
        .on_conflict_do_update(
            index_elements=["user_id", "episode_id"],
            set_={"position": position, "updated_at": now},
        )
        .returning(ReadingProgress.updated_at)
    )
    saved_at: datetime = (await session.execute(statement)).scalar_one()
    return saved_at


async def list_last_read(session: AsyncSession, user_id: UUID) -> list[LastRead]:
    """For each work the reader has been in: the episode they read last, newest first.

    Only published episodes count, so a work with nothing left to read drops
    out, and comes back if it is published again.
    """
    statement = (
        select(
            Episode.work_id,
            Episode.id,
            Episode.number,
            Episode.title,
            ReadingProgress.position,
            ReadingProgress.updated_at,
        )
        .join(Episode, Episode.id == ReadingProgress.episode_id)
        .where(ReadingProgress.user_id == user_id, Episode.status == EpisodeStatus.PUBLISHED)
        .ext(distinct_on(Episode.work_id))
        .order_by(Episode.work_id, ReadingProgress.updated_at.desc())
    )
    entries = [
        LastRead(row[0], row[1], row[2], row[3], row[4], row[5])
        for row in await session.execute(statement)
    ]
    entries.sort(key=lambda entry: entry.read_at, reverse=True)
    return entries[:LIBRARY_LIMIT]


async def add_favourite(session: AsyncSession, user_id: UUID, work_id: UUID) -> None:
    await session.execute(
        insert(Favourite)
        .values(id=uuid7(), user_id=user_id, work_id=work_id)
        .on_conflict_do_nothing(index_elements=["user_id", "work_id"])
    )


async def remove_favourite(session: AsyncSession, user_id: UUID, work_id: UUID) -> None:
    await session.execute(
        delete(Favourite).where(Favourite.user_id == user_id, Favourite.work_id == work_id)
    )


async def list_favourite_work_ids(session: AsyncSession, user_id: UUID) -> Sequence[UUID]:
    # Ids are UUID v7, so id order is the order they were added in.
    statement = (
        select(Favourite.work_id)
        .where(Favourite.user_id == user_id)
        .order_by(Favourite.id.desc())
        .limit(LIBRARY_LIMIT)
    )
    return (await session.execute(statement)).scalars().all()
