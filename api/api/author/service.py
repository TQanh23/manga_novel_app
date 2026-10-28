from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import structlog
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth.models import User
from api.author import repository
from api.catalogue.labels import WorkLabels, labels_for_works, tag_name, tag_slug
from api.catalogue.models import (
    ContentLanguage,
    Episode,
    EpisodeStatus,
    EpisodeVersion,
    GlossaryEntry,
    GlossaryKind,
    TagKind,
    Work,
    WorkType,
)
from api.catalogue.text import plain_text, sanitize_html
from api.core.errors import AppError
from api.core.presets import ConfigPreset, PresetKind

logger = structlog.get_logger(__name__)


MAX_GENRES = 3


@dataclass(frozen=True)
class WorkState:
    """A work with its genres and tags, which live in their own tables."""

    work: Work
    labels: WorkLabels


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


async def _resolve_labels(
    session: AsyncSession,
    work_id: UUID | None,
    *,
    genres: Sequence[str] | None,
    tags: Sequence[str] | None,
) -> set[UUID] | None:
    """The tags a work should carry after this request, or None to leave them.

    `genres` and `tags` each replace their own set; None keeps that set as it
    is. Everything is checked before a tag is created, so a refused request
    writes nothing.
    """
    if genres is None and tags is None:
        return None
    current = await repository.tags_of_work(session, work_id) if work_id is not None else []
    genre_ids = {tag.id for tag in current if tag.kind == TagKind.GENRE}
    tag_ids = {tag.id for tag in current if tag.kind != TagKind.GENRE}

    if genres is not None:
        wanted = set(genres)
        found = await repository.get_genres(session, wanted)
        if len(found) != len(wanted):
            raise AppError("unknown_genre", "Choose from the offered genres", status_code=422)
        genre_ids = {genre.id for genre in found}

    names: dict[str, str] = {}
    if tags is not None:
        # The first spelling of a tag in the request is the one that counts.
        for raw in tags:
            if slug := tag_slug(raw):
                names.setdefault(slug, tag_name(raw))
        # Typing the name of a genre as a tag gives the work that genre.
        genre_ids |= {genre.id for genre in await repository.get_genres(session, set(names))}

    if len(genre_ids) > MAX_GENRES:
        raise AppError("too_many_genres", "A work has at most three genres", status_code=422)
    if tags is not None:
        resolved = await repository.ensure_tags(session, names)
        tag_ids = {tag.id for tag in resolved if tag.kind != TagKind.GENRE}
    return genre_ids | tag_ids


async def _state(session: AsyncSession, work: Work) -> WorkState:
    labels = await labels_for_works(session, [work.id])
    return WorkState(work, labels.get(work.id, WorkLabels()))


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
    genres: Sequence[str] = (),
    tags: Sequence[str] = (),
    is_sample: bool = False,
) -> WorkState:
    """Start a work (FR-NV-01). It is not opted in to training.

    `is_sample` marks text written for this project, which may go to AI
    providers that real manuscripts never reach. Only the seed script passes
    it; no route does.
    """
    if wuf_preset_id is not None:
        await _require_wuf_preset(session, wuf_preset_id)
    label_ids = await _resolve_labels(session, None, genres=genres, tags=tags)

    work = Work(
        author_id=author.id,
        type=type,
        title=title,
        synopsis=synopsis,
        language=language,
        wuf_preset_id=wuf_preset_id,
        is_sample=is_sample,
    )
    session.add(work)
    await session.flush()
    if label_ids:
        await repository.replace_work_tags(session, work.id, label_ids)
    await session.refresh(work)
    state = await _state(session, work)
    await session.commit()
    logger.info("work_created", author_id=str(author.id), work_id=str(work.id))
    return state


async def list_works(session: AsyncSession, *, author: User) -> Sequence[WorkState]:
    works = await repository.list_works(session, author.id)
    labels = await labels_for_works(session, [work.id for work in works])
    return [WorkState(work, labels.get(work.id, WorkLabels())) for work in works]


async def get_work(session: AsyncSession, *, author: User, work_id: UUID) -> WorkState:
    return await _state(session, await _own_work(session, author, work_id))


async def update_work(
    session: AsyncSession, *, author: User, work_id: UUID, changes: Mapping[str, Any]
) -> WorkState:
    """Apply the fields the author sent. `changes` holds only those."""
    work = await _own_work(session, author, work_id, for_update=True)
    # Everything that can be refused is checked before anything is changed.
    if changes.get("wuf_preset_id") is not None:
        await _require_wuf_preset(session, changes["wuf_preset_id"])
    label_ids = await _resolve_labels(
        session, work.id, genres=changes.get("genres"), tags=changes.get("tags")
    )

    for field in ("title", "synopsis", "language", "status"):
        if changes.get(field) is not None:
            setattr(work, field, changes[field])
    # The one field where null means something: no wait-until-free.
    if "wuf_preset_id" in changes:
        work.wuf_preset_id = changes["wuf_preset_id"]
    if label_ids is not None:
        await repository.replace_work_tags(session, work.id, label_ids)

    await session.flush()
    await session.refresh(work)
    state = await _state(session, work)
    await session.commit()
    logger.info("work_updated", author_id=str(author.id), work_id=str(work.id))
    return state


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


async def update_episode(
    session: AsyncSession, *, author: User, episode_id: UUID, title: str | None
) -> EpisodeState:
    """Rename an episode. Readers of a published episode see the new title at once."""
    episode = await _own_episode(session, author, episode_id, for_update=True)
    if episode.status == EpisodeStatus.REMOVED:
        raise AppError("episode_removed", "This episode has been removed", status_code=409)

    if title is not None:
        episode.title = title
    await session.flush()
    await session.refresh(episode)
    latest = await repository.latest_version_ids(session, [episode.id], author_id=author.id)
    await session.commit()
    logger.info("episode_updated", author_id=str(author.id), episode_id=str(episode.id))
    return EpisodeState(episode, latest.get(episode.id))


async def save_draft(
    session: AsyncSession, *, author: User, episode_id: UUID, body_html: str
) -> tuple[EpisodeVersion, Episode]:
    """Save the episode's text as a new version.

    Only the sanitized HTML is stored. Saving what is already the newest
    version, once sanitized, adds nothing, so an editor may autosave as often
    as it likes.
    """
    stored = sanitize_html(body_html)
    # The lock orders concurrent saves, so "same as the newest" is decided once.
    episode = await _own_novel_episode(session, author, episode_id, for_update=True)
    latest = await repository.latest_version(session, episode.id, author_id=author.id)
    if latest is not None and latest.body_html == stored:
        await session.commit()
        return latest, episode

    version = await repository.add_version(session, episode.id, stored, author_id=author.id)
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

    version = await repository.add_version(
        session, episode.id, source.body_html, author_id=author.id
    )
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
    if latest is None or not plain_text(latest.body_html):
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


def _glossary_entry_exists() -> AppError:
    return AppError(
        "glossary_entry_exists",
        "This work already has an entry of that kind with that name",
        status_code=409,
    )


def _unique(names: Sequence[str]) -> list[str]:
    return list(dict.fromkeys(names))


async def list_glossary(
    session: AsyncSession, *, author: User, work_id: UUID
) -> Sequence[GlossaryEntry]:
    work = await _own_work(session, author, work_id)
    return await repository.list_glossary(session, work.id)


async def create_glossary_entry(
    session: AsyncSession,
    *,
    author: User,
    work_id: UUID,
    kind: GlossaryKind,
    name: str,
    aliases: Sequence[str],
    attributes: Mapping[str, Any],
    translations: Mapping[str, str],
) -> GlossaryEntry:
    """Record a character, a place or a term of a work (FR-NV-03)."""
    work = await _own_work(session, author, work_id)
    if await repository.find_glossary_entry(session, work.id, kind, name) is not None:
        raise _glossary_entry_exists()

    entry = GlossaryEntry(
        work_id=work.id,
        kind=kind,
        name=name,
        aliases=_unique(aliases),
        attributes=dict(attributes),
        translations=dict(translations),
    )
    try:
        # A savepoint, so losing a race for the same name undoes only this insert.
        async with session.begin_nested():
            session.add(entry)
            await session.flush()
    except IntegrityError:
        raise _glossary_entry_exists() from None
    await session.refresh(entry)
    await session.commit()
    logger.info(
        "glossary_entry_created",
        author_id=str(author.id),
        work_id=str(work.id),
        entry_id=str(entry.id),
    )
    return entry


async def update_glossary_entry(
    session: AsyncSession,
    *,
    author: User,
    work_id: UUID,
    entry_id: UUID,
    changes: Mapping[str, Any],
) -> GlossaryEntry:
    """Apply the fields the author sent. `changes` holds only those."""
    work = await _own_work(session, author, work_id)
    entry = await repository.get_glossary_entry(session, work.id, entry_id, for_update=True)
    if entry is None:
        raise AppError("glossary_entry_not_found", "Glossary entry not found", status_code=404)

    kind = changes.get("kind") or entry.kind
    name = changes.get("name") or entry.name
    if (kind, name) != (entry.kind, entry.name):
        taken = await repository.find_glossary_entry(session, work.id, kind, name)
        if taken is not None and taken.id != entry.id:
            raise _glossary_entry_exists()

    try:
        # A savepoint, so losing a race for the same name undoes only this change.
        async with session.begin_nested():
            entry.kind, entry.name = kind, name
            if changes.get("aliases") is not None:
                entry.aliases = _unique(changes["aliases"])
            if changes.get("attributes") is not None:
                entry.attributes = dict(changes["attributes"])
            if changes.get("translations") is not None:
                entry.translations = {
                    str(language): text for language, text in changes["translations"].items()
                }
            await session.flush()
    except IntegrityError:
        raise _glossary_entry_exists() from None
    await session.refresh(entry)
    await session.commit()
    logger.info(
        "glossary_entry_updated",
        author_id=str(author.id),
        work_id=str(work.id),
        entry_id=str(entry.id),
    )
    return entry
