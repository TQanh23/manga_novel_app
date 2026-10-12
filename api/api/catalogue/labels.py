"""Genres and tags of works: what both the author API and the catalogue show."""

import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.catalogue.models import Tag, TagKind, WorkTag


@dataclass(frozen=True)
class WorkLabels:
    # Genres by slug (the client translates them), tags by the name they were given.
    genres: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()


def tag_name(raw: str) -> str:
    """A tag as it is stored and shown: one Unicode form, single spaces."""
    return " ".join(unicodedata.normalize("NFKC", raw).split())


def tag_slug(raw: str) -> str:
    """What makes two spellings the same tag: case and spacing do not count.

    Works on characters, not words, so it holds for Korean, Japanese and
    Vietnamese as well as English.
    """
    return tag_name(raw).lower().replace(" ", "-")


async def labels_for_works(
    session: AsyncSession, work_ids: Sequence[UUID]
) -> dict[UUID, WorkLabels]:
    """Genres and tags of each given work. A work without any is left out."""
    if not work_ids:
        return {}
    rows = await session.execute(
        select(WorkTag.work_id, Tag.kind, Tag.slug, Tag.name)
        .join(Tag, Tag.id == WorkTag.tag_id)
        .where(WorkTag.work_id.in_(work_ids))
        .order_by(Tag.slug)
    )
    genres: dict[UUID, list[str]] = {}
    tags: dict[UUID, list[str]] = {}
    for work_id, kind, slug, name in rows:
        if kind == TagKind.GENRE:
            genres.setdefault(work_id, []).append(slug)
        else:
            tags.setdefault(work_id, []).append(name)
    return {
        work_id: WorkLabels(tuple(genres.get(work_id, ())), tuple(tags.get(work_id, ())))
        for work_id in genres.keys() | tags.keys()
    }
