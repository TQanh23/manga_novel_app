"""Queries behind the author API.

Works and episodes are always looked up together with their author, so a
query cannot return another author's row. The functions that touch
episode_versions take author_id and scope the transaction to it first: the
table is under row-level security and shows nothing otherwise.
"""

from collections.abc import Sequence
from datetime import datetime
from uuid import UUID

from sqlalchemy import delete, func, select, update
from sqlalchemy.dialects.postgresql import distinct_on, insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import load_only

from api.catalogue.models import (
    Episode,
    EpisodeStatus,
    EpisodeVersion,
    GlossaryEntry,
    Tag,
    TagKind,
    Work,
    WorkTag,
)
from api.core.db import set_author_context
from api.core.ids import uuid7
from api.core.presets import ConfigPreset, PresetKind


async def get_work_for_author(
    session: AsyncSession, work_id: UUID, author_id: UUID, *, for_update: bool = False
) -> Work | None:
    statement = (
        select(Work)
        .where(Work.id == work_id, Work.author_id == author_id)
        .execution_options(populate_existing=True)
    )
    if for_update:
        statement = statement.with_for_update()
    return (await session.execute(statement)).scalar_one_or_none()


async def list_works(session: AsyncSession, author_id: UUID) -> Sequence[Work]:
    # Ids are UUID v7, so id order is creation order.
    statement = select(Work).where(Work.author_id == author_id).order_by(Work.id.desc())
    return (await session.execute(statement)).scalars().all()


async def get_episode_for_author(
    session: AsyncSession, episode_id: UUID, author_id: UUID, *, for_update: bool = False
) -> tuple[Episode, str] | None:
    """The episode and the type of its work, or None when it is not this author's."""
    statement = (
        select(Episode, Work.type)
        .join(Work, Work.id == Episode.work_id)
        .where(Episode.id == episode_id, Episode.author_id == author_id)
        .execution_options(populate_existing=True)
    )
    if for_update:
        statement = statement.with_for_update(of=Episode)
    row = (await session.execute(statement)).one_or_none()
    return (row[0], row[1]) if row is not None else None


async def list_episodes(session: AsyncSession, work_id: UUID) -> Sequence[Episode]:
    statement = select(Episode).where(Episode.work_id == work_id).order_by(Episode.number)
    return (await session.execute(statement)).scalars().all()


async def next_episode_number(session: AsyncSession, work_id: UUID) -> int:
    """The number after the work's last episode. The caller holds a lock on the work."""
    statement = select(func.coalesce(func.max(Episode.number), 0)).where(Episode.work_id == work_id)
    return int((await session.execute(statement)).scalar_one()) + 1


async def get_genres(session: AsyncSession, slugs: set[str]) -> Sequence[Tag]:
    statement = select(Tag).where(Tag.kind == TagKind.GENRE, Tag.slug.in_(slugs))
    return (await session.execute(statement)).scalars().all()


async def ensure_tags(session: AsyncSession, names_by_slug: dict[str, str]) -> Sequence[Tag]:
    """The tag for each slug, created with the given name where there was none.

    A slug that already exists keeps the name of whoever used it first, and
    may be a genre.
    """
    if not names_by_slug:
        return []
    # ON CONFLICT: two authors may type the same new tag at the same moment.
    await session.execute(
        insert(Tag)
        .values(
            [
                {"id": uuid7(), "slug": slug, "name": name, "kind": TagKind.TAG}
                for slug, name in names_by_slug.items()
            ]
        )
        .on_conflict_do_nothing(index_elements=["slug"])
    )
    statement = select(Tag).where(Tag.slug.in_(names_by_slug))
    return (await session.execute(statement)).scalars().all()


async def tags_of_work(session: AsyncSession, work_id: UUID) -> Sequence[Tag]:
    statement = (
        select(Tag).join(WorkTag, WorkTag.tag_id == Tag.id).where(WorkTag.work_id == work_id)
    )
    return (await session.execute(statement)).scalars().all()


async def replace_work_tags(session: AsyncSession, work_id: UUID, tag_ids: set[UUID]) -> None:
    """Make the work carry exactly these tags, touching only the links that change."""
    current = set(
        (await session.execute(select(WorkTag.tag_id).where(WorkTag.work_id == work_id))).scalars()
    )
    if removed := current - tag_ids:
        await session.execute(
            delete(WorkTag).where(WorkTag.work_id == work_id, WorkTag.tag_id.in_(removed))
        )
    session.add_all(WorkTag(work_id=work_id, tag_id=tag_id) for tag_id in tag_ids - current)
    await session.flush()


async def publish_due_episodes(session: AsyncSession, now: datetime) -> Sequence[UUID]:
    """Publish every scheduled episode whose time has come; returns their ids.

    One statement, so it is safe to run twice or from two workers at once: an
    episode matches while it is still scheduled, and only one update gets it.
    It reads no draft. The version to show was fixed when the episode was
    scheduled.
    """
    statement = (
        update(Episode)
        .where(Episode.status == EpisodeStatus.SCHEDULED, Episode.publish_at <= now)
        .values(status=EpisodeStatus.PUBLISHED)
        .returning(Episode.id)
        .execution_options(synchronize_session=False)
    )
    return (await session.execute(statement)).scalars().all()


async def get_active_preset(
    session: AsyncSession, preset_id: UUID, kind: PresetKind
) -> ConfigPreset | None:
    statement = select(ConfigPreset).where(
        ConfigPreset.id == preset_id, ConfigPreset.kind == kind, ConfigPreset.active
    )
    return (await session.execute(statement)).scalar_one_or_none()


async def list_active_presets(session: AsyncSession, kind: PresetKind) -> Sequence[ConfigPreset]:
    statement = (
        select(ConfigPreset)
        .where(ConfigPreset.kind == kind, ConfigPreset.active)
        .order_by(ConfigPreset.value)
    )
    return (await session.execute(statement)).scalars().all()


async def latest_version(
    session: AsyncSession, episode_id: UUID, *, author_id: UUID
) -> EpisodeVersion | None:
    await set_author_context(session, author_id)
    # Ids are generated when the row is added, so the highest id is the last save.
    statement = (
        select(EpisodeVersion)
        .where(EpisodeVersion.episode_id == episode_id)
        .order_by(EpisodeVersion.id.desc())
        .limit(1)
    )
    return (await session.execute(statement)).scalar_one_or_none()


async def latest_version_ids(
    session: AsyncSession, episode_ids: Sequence[UUID], *, author_id: UUID
) -> dict[UUID, UUID]:
    """The newest version of each episode that has one, keyed by episode."""
    if not episode_ids:
        return {}
    await set_author_context(session, author_id)
    statement = (
        select(EpisodeVersion.episode_id, EpisodeVersion.id)
        .where(EpisodeVersion.episode_id.in_(episode_ids))
        .ext(distinct_on(EpisodeVersion.episode_id))
        .order_by(EpisodeVersion.episode_id, EpisodeVersion.id.desc())
    )
    return {row.episode_id: row.id for row in await session.execute(statement)}


async def list_versions(
    session: AsyncSession,
    episode_id: UUID,
    *,
    author_id: UUID,
    limit: int,
    before: UUID | None,
) -> Sequence[EpisodeVersion]:
    """Newest first, without the text. `before` continues below a version already seen."""
    await set_author_context(session, author_id)
    statement = (
        select(EpisodeVersion)
        .options(load_only(EpisodeVersion.id, EpisodeVersion.created_at))
        .where(EpisodeVersion.episode_id == episode_id)
        .order_by(EpisodeVersion.id.desc())
        .limit(limit)
    )
    if before is not None:
        statement = statement.where(EpisodeVersion.id < before)
    return (await session.execute(statement)).scalars().all()


async def get_version(
    session: AsyncSession, episode_id: UUID, version_id: UUID, *, author_id: UUID
) -> EpisodeVersion | None:
    await set_author_context(session, author_id)
    statement = (
        select(EpisodeVersion)
        .where(EpisodeVersion.id == version_id, EpisodeVersion.episode_id == episode_id)
        .execution_options(populate_existing=True)
    )
    return (await session.execute(statement)).scalar_one_or_none()


async def add_version(
    session: AsyncSession, episode_id: UUID, body_md: str, *, author_id: UUID
) -> EpisodeVersion:
    await set_author_context(session, author_id)
    version = EpisodeVersion(
        episode_id=episode_id, author_id=author_id, body_md=body_md, created_by=author_id
    )
    session.add(version)
    # Written and read back here, while the author context is set.
    await session.flush()
    await session.refresh(version)
    return version


async def list_glossary(session: AsyncSession, work_id: UUID) -> Sequence[GlossaryEntry]:
    statement = (
        select(GlossaryEntry)
        .where(GlossaryEntry.work_id == work_id)
        .order_by(GlossaryEntry.kind, GlossaryEntry.name)
    )
    return (await session.execute(statement)).scalars().all()


async def get_glossary_entry(
    session: AsyncSession, work_id: UUID, entry_id: UUID, *, for_update: bool = False
) -> GlossaryEntry | None:
    """An entry of the given work. An entry of another work is not found."""
    statement = (
        select(GlossaryEntry)
        .where(GlossaryEntry.id == entry_id, GlossaryEntry.work_id == work_id)
        .execution_options(populate_existing=True)
    )
    if for_update:
        statement = statement.with_for_update()
    return (await session.execute(statement)).scalar_one_or_none()


async def find_glossary_entry(
    session: AsyncSession, work_id: UUID, kind: str, name: str
) -> GlossaryEntry | None:
    statement = select(GlossaryEntry).where(
        GlossaryEntry.work_id == work_id, GlossaryEntry.kind == kind, GlossaryEntry.name == name
    )
    return (await session.execute(statement)).scalar_one_or_none()
