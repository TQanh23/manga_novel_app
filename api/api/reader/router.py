from uuid import UUID

from fastapi import APIRouter, Depends, status

from api.auth.deps import CurrentUser, OptionalUser, Session, limit_by_user
from api.core.config import get_settings
from api.core.rate_limit import limit_by_ip
from api.reader import service
from api.reader.schemas import (
    EpisodeContentResponse,
    LibraryResponse,
    ProgressResponse,
    ProgressSave,
)

router = APIRouter(tags=["reader"])

_limit_reads = Depends(
    limit_by_ip("reader", limit=lambda: get_settings().rate_limit_catalogue_per_ip)
)
_limit_writes = Depends(
    limit_by_user("reader-write", limit=lambda: get_settings().rate_limit_reader_writes_per_user)
)


@router.get(
    "/episodes/{episode_id}/content",
    operation_id="reader_get_episode_content",
    dependencies=[_limit_reads],
)
async def get_episode_content(
    episode_id: UUID, reader: OptionalUser, session: Session
) -> EpisodeContentResponse:
    content = await service.get_content(session, episode_id, reader=reader)
    return EpisodeContentResponse.from_content(content)


@router.put(
    "/progress/{episode_id}", operation_id="reader_save_progress", dependencies=[_limit_writes]
)
async def save_progress(
    episode_id: UUID, payload: ProgressSave, reader: CurrentUser, session: Session
) -> ProgressResponse:
    progress = await service.save_progress(
        session, reader=reader, episode_id=episode_id, position=payload.position
    )
    return ProgressResponse.from_progress(progress)


@router.get("/library", operation_id="reader_get_library")
async def get_library(reader: CurrentUser, session: Session) -> LibraryResponse:
    return LibraryResponse.from_library(await service.get_library(session, reader=reader))


@router.put(
    "/favourites/{work_id}",
    operation_id="reader_add_favourite",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[_limit_writes],
)
async def add_favourite(work_id: UUID, reader: CurrentUser, session: Session) -> None:
    await service.add_favourite(session, reader=reader, work_id=work_id)


@router.delete(
    "/favourites/{work_id}",
    operation_id="reader_remove_favourite",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[_limit_writes],
)
async def remove_favourite(work_id: UUID, reader: CurrentUser, session: Session) -> None:
    await service.remove_favourite(session, reader=reader, work_id=work_id)
