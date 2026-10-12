from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import StringConstraints

from api.auth.deps import Session
from api.catalogue import service
from api.catalogue.models import WorkStatus, WorkType
from api.catalogue.schemas import (
    EpisodeSummary,
    GenreResponse,
    WorkCard,
    WorkDetail,
    WorkPage,
    WorkSort,
)
from api.core.config import get_settings
from api.core.rate_limit import limit_by_ip

# Public: guests browse and search without signing in.
router = APIRouter(
    tags=["catalogue"],
    dependencies=[
        Depends(limit_by_ip("catalogue", limit=lambda: get_settings().rate_limit_catalogue_per_ip))
    ],
)

Limit = Annotated[int, Query(ge=1, le=50)]
Offset = Annotated[int, Query(ge=0, le=10_000)]
SearchText = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100), Query()
]


@router.get("/works", operation_id="catalogue_list_works")
async def list_works(
    session: Session,
    type: WorkType | None = None,
    genre: str | None = None,
    status: WorkStatus | None = None,
    sort: WorkSort = WorkSort.NEWEST,
    limit: Limit = 20,
    offset: Offset = 0,
) -> WorkPage:
    works, has_more = await service.list_works(
        session,
        type=type,
        genre=genre,
        status=status,
        by_popularity=sort == WorkSort.POPULAR,
        limit=limit,
        offset=offset,
    )
    return WorkPage(items=[WorkCard.from_work(work) for work in works], has_more=has_more)


@router.get("/works/{work_id}", operation_id="catalogue_get_work")
async def get_work(work_id: UUID, session: Session) -> WorkDetail:
    return WorkDetail.from_work(await service.get_work(session, work_id))


@router.get("/works/{work_id}/episodes", operation_id="catalogue_list_episodes")
async def list_episodes(work_id: UUID, session: Session) -> list[EpisodeSummary]:
    episodes = await service.list_episodes(session, work_id)
    return [EpisodeSummary.from_episode(episode) for episode in episodes]


@router.get("/search", operation_id="catalogue_search_works")
async def search_works(
    q: SearchText, session: Session, limit: Limit = 20, offset: Offset = 0
) -> WorkPage:
    works, has_more = await service.search_works(session, q, limit=limit, offset=offset)
    return WorkPage(items=[WorkCard.from_work(work) for work in works], has_more=has_more)


@router.get("/genres", operation_id="catalogue_list_genres")
async def list_genres(session: Session) -> list[GenreResponse]:
    return [GenreResponse.from_tag(genre) for genre in await service.list_genres(session)]
