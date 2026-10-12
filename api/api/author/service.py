from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth.models import User
from api.author import repository
from api.catalogue.models import (
    ContentLanguage,
    Episode,
    EpisodeStatus,
    EpisodeVersion,
    Work,
    WorkType,
)
from api.core.errors import AppError
from api.core.presets import ConfigPreset, PresetKind

logger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class EpisodeState:
    """An episode and its newest save, which the episode row does not record."""

    episode: Episode
    latest_version_id: UUID | None


# Another author's work answers exactly like one that does not exist, so ids
# cannot be probed.
def _work_not_found() -> AppError:
    return AppError("work_not_found", "Work not found", status_code=404)


def _episode_not_found() -> AppError:
    return AppError("episode_not_found", "Episode not found", status_code=404)


def _version_not_found() -> AppError:
    return AppError("version_not_found", "Version not found", status_code=404)


async def _own_work(
    session: AsyncSession, author: User, work_id: UUID, *, for_update: bool = False
) -> Work:
    work = await repository.get_work_for_author(session, work_id, author.id, for_update=for_update)
    if work is None:
        raise _work_not_found()
    return work


async def _own_episode(
    session: AsyncSession, author: User, episode_id: UUID, *, for_update: bool = False
) -> Episode:
    found = await repository.get_episode_for_author(
        session, episode_id, author.id, for_update=for_update
    )
    if found is None:
        raise _episode_not_found()
    return found[0]


async def _own_novel_episode(
    session: AsyncSession, author: User, episode_id: UUID, *, for_update: bool = False
) -> Episode:
    """An episode whose content is text. A manga episode is made of pages instead."""
    found = await repository.get_episode_for_author(
        session, episode_id, author.id, for_update=for_update
    )
    if found is None:
        raise _episode_not_found()
    episode, work_type = found
    if work_type != WorkType.NOVEL:
        raise AppError("not_a_novel", "Only novel episodes have a text draft", status_code=409)
    return episode


async def _require_wuf_preset(session: AsyncSession, preset_id: UUID) -> None:
    # The foreign key accepts any preset; only the service knows the column
    # wants a wait-until-free period that is still offered.
    if await repository.get_active_preset(session, preset_id, PresetKind.WUF_PERIOD) is None:
        raise AppError(
            "invalid_wuf_preset",
            "Choose one of the offered wait-until-free periods",
            status_code=422,
        )


async def list_wuf_presets(session: AsyncSession) -> Sequence[ConfigPreset]:
    return await repository.list_active_presets(session, PresetKind.WUF_PERIOD)


async def create_work(
    session: AsyncSession,
    *,
    author: User,
    type: WorkType,
    title: str,
    synopsis: str,
    language: ContentLanguage,
    wuf_preset_id: UUID | None,
) -> Work:
    """Start a work (FR-NV-01). It is not a sample and not opted in to training."""
    if wuf_preset_id is not None:
        await _require_wuf_preset(session, wuf_preset_id)

    work = Work(
        author_id=author.id,
        type=type,
        title=title,
        synopsis=synopsis,
        language=language,
        wuf_preset_id=wuf_preset_id,
    )
    session.add(work)
    await session.flush()
    await session.refresh(work)
    await session.commit()
    logger.info("work_created", author_id=str(author.id), work_id=str(work.id))
    return work


async def list_works(session: AsyncSession, *, author: User) -> Sequence[Work]:
    return await repository.list_works(session, author.id)


async def get_work(session: AsyncSession, *, author: User, work_id: UUID) -> Work:
    return await _own_work(session, author, work_id)


async def update_work(
    session: AsyncSession, *, author: User, work_id: UUID, changes: Mapping[str, Any]
) -> Work:
    """Apply the fields the author sent. `changes` holds only those."""
    work = await _own_work(session, author, work_id, for_update=True)

    for field in ("title", "synopsis", "language", "status"):
        if changes.get(field) is not None:
            setattr(work, field, changes[field])
    # The one field where null means something: no wait-until-free.
    if "wuf_preset_id" in changes:
        if changes["wuf_preset_id"] is not None:
            await _require_wuf_preset(session, changes["wuf_preset_id"])
        work.wuf_preset_id = changes["wuf_preset_id"]

    await session.flush()
    await session.refresh(work)
    await session.commit()
    logger.info("work_updated", author_id=str(author.id), work_id=str(work.id))
    return work


async def create_episode(
    session: AsyncSession, *, author: User, work_id: UUID, title: str
) -> EpisodeState:
    """Add the next episode of a work, as a free draft."""
    # Locking the work makes two concurrent requests take different numbers.
    work = await _own_work(session, author, work_id, for_update=True)
    episode = Episode(
        work_id=work.id,
        author_id=author.id,
        number=await repository.next_episode_number(session, work.id),
        title=title,
    )
    session.add(episode)
    await session.flush()
    await session.refresh(episode)
    await session.commit()
    logger.info(
        "episode_created",
        author_id=str(author.id),
        work_id=str(work.id),
        episode_id=str(episode.id),
    )
    return EpisodeState(episode, None)


async def list_episodes(
    session: AsyncSession, *, author: User, work_id: UUID
) -> Sequence[EpisodeState]:
    work = await _own_work(session, author, work_id)
    episodes = await repository.list_episodes(session, work.id)
    latest = await repository.latest_version_ids(
        session, [episode.id for episode in episodes], author_id=author.id
    )
    return [EpisodeState(episode, latest.get(episode.id)) for episode in episodes]


async def get_episode(session: AsyncSession, *, author: User, episode_id: UUID) -> EpisodeState:
    episode = await _own_episode(session, author, episode_id)
    latest = await repository.latest_version_ids(session, [episode.id], author_id=author.id)
    return EpisodeState(episode, latest.get(episode.id))


async def save_draft(
    session: AsyncSession, *, author: User, episode_id: UUID, body_md: str
) -> tuple[EpisodeVersion, Episode]:
    """Save the episode's text as a new version.

    Saving what is already the newest version adds nothing, so an editor may
    autosave as often as it likes.
    """
    # The lock orders concurrent saves, so "same as the newest" is decided once.
    episode = await _own_novel_episode(session, author, episode_id, for_update=True)
    latest = await repository.latest_version(session, episode.id, author_id=author.id)
    if latest is not None and latest.body_md == body_md:
        await session.commit()
        return latest, episode

    version = await repository.add_version(session, episode.id, body_md, author_id=author.id)
    await session.commit()
    logger.info(
        "draft_saved",
        author_id=str(author.id),
        episode_id=str(episode.id),
        version_id=str(version.id),
    )
    return version, episode


async def get_draft(
    session: AsyncSession, *, author: User, episode_id: UUID
) -> EpisodeVersion | None:
    episode = await _own_novel_episode(session, author, episode_id)
    return await repository.latest_version(session, episode.id, author_id=author.id)


async def list_versions(
    session: AsyncSession, *, author: User, episode_id: UUID, limit: int, before: UUID | None
) -> tuple[Sequence[EpisodeVersion], Episode]:
    episode = await _own_novel_episode(session, author, episode_id)
    versions = await repository.list_versions(
        session, episode.id, author_id=author.id, limit=limit, before=before
    )
    return versions, episode


async def get_version(
    session: AsyncSession, *, author: User, episode_id: UUID, version_id: UUID
) -> tuple[EpisodeVersion, Episode]:
    episode = await _own_novel_episode(session, author, episode_id)
    version = await repository.get_version(session, episode.id, version_id, author_id=author.id)
    if version is None:
        raise _version_not_found()
    return version, episode


async def restore_version(
    session: AsyncSession, *, author: User, episode_id: UUID, version_id: UUID
) -> tuple[EpisodeVersion, Episode]:
    """Make an old version the newest save again.

    Versions are never rewritten: restoring adds a version with the old text,
    and everything saved since stays in the history.
    """
    episode = await _own_novel_episode(session, author, episode_id, for_update=True)
    source = await repository.get_version(session, episode.id, version_id, author_id=author.id)
    if source is None:
        raise _version_not_found()

    version = await repository.add_version(session, episode.id, source.body_md, author_id=author.id)
    await session.commit()
    logger.info(
        "version_restored",
        author_id=str(author.id),
        episode_id=str(episode.id),
        version_id=str(version.id),
        restored_from=str(source.id),
    )
    return version, episode


async def _version_to_publish(
    session: AsyncSession, author: User, episode: Episode
) -> EpisodeVersion:
    """The newest save of an episode that may go live, or the reason it may not."""
    if episode.status == EpisodeStatus.REMOVED:
        raise AppError("episode_removed", "This episode has been removed", status_code=409)

    # Always this episode's own newest version, so the pointer cannot name
    # another episode's text.
    latest = await repository.latest_version(session, episode.id, author_id=author.id)
    if latest is None or not latest.body_md.strip():
        raise AppError("nothing_to_publish", "Save some text before publishing", status_code=409)
    return latest


async def publish_episode(session: AsyncSession, *, author: User, episode_id: UUID) -> EpisodeState:
    """Show readers the newest save, now (FR-NV-01).

    Publishing again after more saves moves readers to the newest one and
    keeps the time the episode first went live.
    """
    episode = await _own_novel_episode(session, author, episode_id, for_update=True)
    latest = await _version_to_publish(session, author, episode)

    if episode.status != EpisodeStatus.PUBLISHED:
        episode.publish_at = datetime.now(UTC)
    episode.status = EpisodeStatus.PUBLISHED
    episode.published_version_id = latest.id
    await session.flush()
    await session.refresh(episode)
    await session.commit()
    logger.info(
        "episode_published",
        author_id=str(author.id),
        episode_id=str(episode.id),
        version_id=str(latest.id),
    )
    return EpisodeState(episode, latest.id)


async def schedule_episode(
    session: AsyncSession, *, author: User, episode_id: UUID, publish_at: datetime
) -> EpisodeState:
    """Have the episode go live on its own at `publish_at` (FR-NV-02).

    The newest save is fixed as the one that will go live. Saves made after
    this stay private; scheduling again picks up the newest one.
    """
    episode = await _own_novel_episode(session, author, episode_id, for_update=True)
    if episode.status == EpisodeStatus.PUBLISHED:
        raise AppError("already_published", "This episode is already published", status_code=409)
    latest = await _version_to_publish(session, author, episode)
    if publish_at <= datetime.now(UTC):
        raise AppError("publish_at_in_past", "Choose a time in the future", status_code=422)

    episode.status = EpisodeStatus.SCHEDULED
    episode.publish_at = publish_at
    # Readers cannot see it yet: a version is public only once its episode is.
    episode.published_version_id = latest.id
    await session.flush()
    await session.refresh(episode)
    await session.commit()
    logger.info(
        "episode_scheduled",
        author_id=str(author.id),
        episode_id=str(episode.id),
        version_id=str(latest.id),
    )
    return EpisodeState(episode, latest.id)


async def unschedule_episode(
    session: AsyncSession, *, author: User, episode_id: UUID
) -> EpisodeState:
    """Call off a scheduled publication; the episode is a draft again."""
    episode = await _own_novel_episode(session, author, episode_id, for_update=True)
    if episode.status != EpisodeStatus.SCHEDULED:
        raise AppError("not_scheduled", "This episode is not scheduled", status_code=409)

    episode.status = EpisodeStatus.DRAFT
    episode.publish_at = None
    episode.published_version_id = None
    await session.flush()
    await session.refresh(episode)
    latest = await repository.latest_version_ids(session, [episode.id], author_id=author.id)
    await session.commit()
    logger.info("episode_unscheduled", author_id=str(author.id), episode_id=str(episode.id))
    return EpisodeState(episode, latest.get(episode.id))


async def publish_due_episodes(
    session: AsyncSession, *, now: datetime | None = None
) -> Sequence[UUID]:
    """Publish the scheduled episodes whose time has come. Run by the worker every minute.

    Safe to run twice, and after a missed run: whatever is overdue goes live
    the next time this runs. `now` is for tests.
    """
    published = await repository.publish_due_episodes(session, now or datetime.now(UTC))
    await session.commit()
    if published:
        logger.info(
            "scheduled_episodes_published",
            count=len(published),
            episode_ids=[str(episode_id) for episode_id in published],
        )
    return published
