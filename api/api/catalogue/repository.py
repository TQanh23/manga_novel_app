"""Queries behind the public catalogue.

What a reader may see is decided in one place, `_visible_works`: a work is in
the catalogue while it has at least one published episode, and only its
published episodes are listed. Every query here starts from that, so a draft,
a scheduled or a removed episode cannot show up by being forgotten in one of
them.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import ColumnElement, Select, Text, case, exists, func, literal_column, or_, select
from sqlalchemy.engine import Row
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import QueryableAttribute

from api.auth.models import User
from api.catalogue.models import Episode, EpisodeStatus, Tag, TagKind, Work, WorkTag


@dataclass(frozen=True)
class ListedWork:
    work: Work
    author_name: str
    # Published episodes only.
    episode_count: int
    last_published_at: datetime


_published = (
    select(
        Episode.work_id,
        func.count().label("episode_count"),
        func.max(Episode.publish_at).label("last_published_at"),
    )
    .where(Episode.status == EpisodeStatus.PUBLISHED)
    .group_by(Episode.work_id)
    .subquery("published")
)


def _visible_works() -> Select[Work, str, int, datetime]:
    """The works a reader may see, each with its author and published-episode figures."""
    return (
        select(Work, User.display_name, _published.c.episode_count, _published.c.last_published_at)
        # The inner join is the rule: no published episode, no row.
        .join(_published, _published.c.work_id == Work.id)
        .join(User, User.id == Work.author_id)
    )


def _listed(row: Row[Work, str, int, datetime]) -> ListedWork:
    return ListedWork(row[0], row[1], row[2], row[3])


async def _page(
    session: AsyncSession,
    statement: Select[Work, str, int, datetime],
    *,
    limit: int,
    offset: int,
) -> tuple[list[ListedWork], bool]:
    # One row more than asked for tells whether there is a next page.
    rows = (await session.execute(statement.limit(limit + 1).offset(offset))).all()
    works = [_listed(row) for row in rows[:limit]]
    return works, len(rows) > limit


async def list_works(
    session: AsyncSession,
    *,
    type: str | None,
    genre: str | None,
    status: str | None,
    by_popularity: bool,
    limit: int,
    offset: int,
) -> tuple[list[ListedWork], bool]:
    statement = _visible_works()
    if type is not None:
        statement = statement.where(Work.type == type)
    if status is not None:
        statement = statement.where(Work.status == status)
    if genre is not None:
        statement = statement.where(
            exists()
            .where(WorkTag.work_id == Work.id, WorkTag.tag_id == Tag.id)
            .where(Tag.kind == TagKind.GENRE, Tag.slug == genre)
        )
    newest_first = (_published.c.last_published_at.desc(), Work.id.desc())
    if by_popularity:
        statement = statement.order_by(_published.c.episode_count.desc(), *newest_first)
    else:
        statement = statement.order_by(*newest_first)
    return await _page(session, statement, limit=limit, offset=offset)


async def get_work(session: AsyncSession, work_id: UUID) -> ListedWork | None:
    row = (await session.execute(_visible_works().where(Work.id == work_id))).one_or_none()
    return _listed(row) if row is not None else None


async def list_published_episodes(session: AsyncSession, work_id: UUID) -> Sequence[Episode]:
    statement = (
        select(Episode)
        .where(Episode.work_id == work_id, Episode.status == EpisodeStatus.PUBLISHED)
        .order_by(Episode.number)
    )
    return (await session.execute(statement)).scalars().all()


async def list_genres(session: AsyncSession) -> Sequence[Tag]:
    statement = select(Tag).where(Tag.kind == TagKind.GENRE).order_by(Tag.slug)
    return (await session.execute(statement)).scalars().all()


def _normalized(value: QueryableAttribute[str] | str) -> ColumnElement[str]:
    # The function the trigram indexes are built on: NFC, no diacritics, lower case.
    return func.core.search_normalize(value, type_=Text)


def _escape_like(value: str) -> str:
    # The reader's text is matched literally: % and _ are not wildcards.
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


async def search_works(
    session: AsyncSession, query: str, *, limit: int, offset: int
) -> tuple[list[ListedWork], bool]:
    """Works whose title, author's name or a tag contains the query.

    Matching ignores case and diacritics, so "kiem si" and "Kiếm sĩ" both find
    "Kiếm sĩ dưới trăng". It compares characters, not words, so it works for
    Japanese and Korean, which have no spaces to split on. Titles that match
    with their diacritics come first, then other title matches, then matches
    on the author or a tag.
    """
    escaped = _escape_like(query)
    contains = func.concat("%", _normalized(escaped), "%")
    contains_as_typed = func.concat("%", func.lower(escaped), "%")

    title_matches = _normalized(Work.title).like(contains, escape="\\")
    title_matches_as_typed = func.lower(
        func.normalize(Work.title, literal_column("NFC")), type_=Text
    ).like(contains_as_typed, escape="\\")
    author_matches = _normalized(User.display_name).like(contains, escape="\\")
    tag_matches = (
        exists()
        .where(WorkTag.work_id == Work.id, WorkTag.tag_id == Tag.id)
        .where(_normalized(Tag.name).like(contains, escape="\\"))
    )

    statement = (
        _visible_works()
        .where(or_(title_matches, author_matches, tag_matches))
        .order_by(
            case((title_matches_as_typed, 0), (title_matches, 1), else_=2),
            _published.c.last_published_at.desc(),
            Work.id.desc(),
        )
    )
    return await _page(session, statement, limit=limit, offset=offset)
