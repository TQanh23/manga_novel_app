from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth.models import User
from api.catalogue import service as catalogue_service
from api.catalogue.models import Episode, WorkType
from api.catalogue.service import CatalogueWork
from api.catalogue.text import split_paragraphs
from api.core.errors import AppError
from api.reader import repository
from api.reader.repository import LastRead

logger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class EpisodeContent:
    episode: Episode
    paragraphs: list[str]
    previous_episode_id: UUID | None
    next_episode_id: UUID | None
    # Where the caller stopped, when they are signed in and have read it before.
    position: int | None


@dataclass(frozen=True)
class SavedProgress:
    episode_id: UUID
    position: int
    saved_at: datetime


@dataclass(frozen=True)
class ReadingEntry:
    work: CatalogueWork
    last_read: LastRead


@dataclass(frozen=True)
class Library:
    reading: list[ReadingEntry]
    favourites: list[CatalogueWork]


def _episode_not_found() -> AppError:
    # A draft, a scheduled or a removed episode answers like one that does not exist.
    return AppError("episode_not_found", "Episode not found", status_code=404)


async def _readable_episode(session: AsyncSession, episode_id: UUID) -> Episode:
    """A published novel episode that is free to read, or the reason it is not."""
    found = await repository.get_published_episode(session, episode_id)
    if found is None:
        raise _episode_not_found()
    episode, work_type = found
    if work_type != WorkType.NOVEL:
        raise AppError("not_a_novel", "Only novel episodes can be read as text", status_code=409)
    # Nothing can unlock a paid episode before billing exists, so nobody reads
    # one: its text must not leak in the meantime.
    if episode.price_coins > 0:
        raise AppError("episode_locked", "Unlock this episode to read it", status_code=402)
    return episode


async def get_content(
    session: AsyncSession, episode_id: UUID, *, reader: User | None
) -> EpisodeContent:
    """What a reader sees of an episode (FR-RD-03). Guests may read free episodes."""
    episode = await _readable_episode(session, episode_id)
    body_md = (
        await repository.get_published_text(session, episode.published_version_id)
        if episode.published_version_id is not None
        else None
    )
    if body_md is None:
        raise _episode_not_found()

    previous_id, next_id = await repository.neighbours(session, episode)
    position = (
        await repository.get_position(session, reader.id, episode.id)
        if reader is not None
        else None
    )
    return EpisodeContent(episode, split_paragraphs(body_md), previous_id, next_id, position)


async def save_progress(
    session: AsyncSession, *, reader: User, episode_id: UUID, position: int
) -> SavedProgress:
    """Remember where the reader is, for all their devices (FR-RD-05).

    The position is not checked against the episode's length: the author may
    publish a shorter text later, so clients clamp it when they open the episode.
    """
    episode = await _readable_episode(session, episode_id)
    saved_at = await repository.save_position(session, reader.id, episode.id, position)
    await session.commit()
    return SavedProgress(episode.id, position, saved_at)


async def get_library(session: AsyncSession, *, reader: User) -> Library:
    """What the reader is reading and what they keep (FR-RD-05)."""
    last_read = await repository.list_last_read(session, reader.id)
    favourite_ids = await repository.list_favourite_work_ids(session, reader.id)
    # Through the catalogue, so its rule applies here too: a work with nothing
    # published is not shown, though the reader's rows for it are kept.
    works = await catalogue_service.get_visible_works(
        session, [*{entry.work_id for entry in last_read}, *favourite_ids]
    )
    return Library(
        reading=[
            ReadingEntry(works[entry.work_id], entry)
            for entry in last_read
            if entry.work_id in works
        ],
        favourites=[works[work_id] for work_id in favourite_ids if work_id in works],
    )


async def add_favourite(session: AsyncSession, *, reader: User, work_id: UUID) -> None:
    """Keep a work in the library. Doing it twice changes nothing."""
    # 404 for a work that is not in the catalogue, like the catalogue itself.
    await catalogue_service.get_work(session, work_id)
    await repository.add_favourite(session, reader.id, work_id)
    await session.commit()
    logger.info("favourite_added", user_id=str(reader.id), work_id=str(work_id))


async def remove_favourite(session: AsyncSession, *, reader: User, work_id: UUID) -> None:
    """Take a work out of the library. Fine if it was not there."""
    await repository.remove_favourite(session, reader.id, work_id)
    await session.commit()
    logger.info("favourite_removed", user_id=str(reader.id), work_id=str(work_id))
