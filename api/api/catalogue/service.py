import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from api.catalogue import repository
from api.catalogue.labels import WorkLabels, labels_for_works
from api.catalogue.models import Episode, Tag
from api.catalogue.repository import ListedWork
from api.core.errors import AppError


@dataclass(frozen=True)
class CatalogueWork:
    listed: ListedWork
    labels: WorkLabels


def _work_not_found() -> AppError:
    # A work with nothing published answers like one that does not exist.
    return AppError("work_not_found", "Work not found", status_code=404)


async def _with_labels(session: AsyncSession, works: Sequence[ListedWork]) -> list[CatalogueWork]:
    labels = await labels_for_works(session, [listed.work.id for listed in works])
    return [CatalogueWork(listed, labels.get(listed.work.id, WorkLabels())) for listed in works]


async def list_works(
    session: AsyncSession,
    *,
    type: str | None,
    genre: str | None,
    status: str | None,
    by_popularity: bool,
    limit: int,
    offset: int,
) -> tuple[list[CatalogueWork], bool]:
    """A page of the catalogue (FR-RD-01)."""
    works, has_more = await repository.list_works(
        session,
        type=type,
        genre=genre,
        status=status,
        by_popularity=by_popularity,
        limit=limit,
        offset=offset,
    )
    return await _with_labels(session, works), has_more


async def get_work(session: AsyncSession, work_id: UUID) -> CatalogueWork:
    """A work's page (FR-RD-02)."""
    listed = await repository.get_work(session, work_id)
    if listed is None:
        raise _work_not_found()
    return (await _with_labels(session, [listed]))[0]


async def get_visible_works(
    session: AsyncSession, work_ids: Sequence[UUID]
) -> dict[UUID, CatalogueWork]:
    """The given works as the catalogue shows them. One a reader may not see is left out."""
    works = await _with_labels(session, await repository.get_works(session, work_ids))
    return {work.listed.work.id: work for work in works}


async def list_episodes(session: AsyncSession, work_id: UUID) -> Sequence[Episode]:
    if await repository.get_work(session, work_id) is None:
        raise _work_not_found()
    return await repository.list_published_episodes(session, work_id)


async def search_works(
    session: AsyncSession, query: str, *, limit: int, offset: int
) -> tuple[list[CatalogueWork], bool]:
    """Search by title, author or tag (FR-RD-06)."""
    # One Unicode form, so text typed with combining marks matches precomposed text.
    works, has_more = await repository.search_works(
        session, unicodedata.normalize("NFC", query), limit=limit, offset=offset
    )
    return await _with_labels(session, works), has_more


async def list_genres(session: AsyncSession) -> Sequence[Tag]:
    return await repository.list_genres(session)
