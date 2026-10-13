from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from api.auth.deps import Session, limit_by_user, require_role
from api.auth.models import Role, User
from api.author import service
from api.author.schemas import (
    DraftSave,
    EpisodeCreate,
    EpisodeDraft,
    EpisodeResponse,
    EpisodeSchedule,
    EpisodeUpdate,
    EpisodeVersionDetail,
    EpisodeVersionSummary,
    GlossaryEntryCreate,
    GlossaryEntryResponse,
    GlossaryEntryUpdate,
    WorkCreate,
    WorkResponse,
    WorkUpdate,
    WufPresetResponse,
)
from api.core.config import get_settings

router = APIRouter(prefix="/author", tags=["author"])

# Admins are not authors: holding only the admin role gives no way in here,
# which is what keeps unpublished drafts out of their reach.
Author = Annotated[User, Depends(require_role(Role.AUTHOR))]

_limit_writes = Depends(
    limit_by_user("author-write", limit=lambda: get_settings().rate_limit_author_writes_per_user)
)


@router.get("/wuf-presets", operation_id="author_list_wuf_presets")
async def list_wuf_presets(author: Author, session: Session) -> list[WufPresetResponse]:
    presets = await service.list_wuf_presets(session)
    return [WufPresetResponse.from_preset(preset) for preset in presets]


@router.post(
    "/works",
    operation_id="author_create_work",
    status_code=status.HTTP_201_CREATED,
    dependencies=[_limit_writes],
)
async def create_work(payload: WorkCreate, author: Author, session: Session) -> WorkResponse:
    state = await service.create_work(
        session,
        author=author,
        type=payload.type,
        title=payload.title,
        synopsis=payload.synopsis,
        language=payload.language,
        wuf_preset_id=payload.wuf_preset_id,
        genres=payload.genres,
        tags=payload.tags,
    )
    return WorkResponse.from_work(state.work, state.labels)


@router.get("/works", operation_id="author_list_works")
async def list_works(author: Author, session: Session) -> list[WorkResponse]:
    states = await service.list_works(session, author=author)
    return [WorkResponse.from_work(state.work, state.labels) for state in states]


@router.get("/works/{work_id}", operation_id="author_get_work")
async def get_work(work_id: UUID, author: Author, session: Session) -> WorkResponse:
    state = await service.get_work(session, author=author, work_id=work_id)
    return WorkResponse.from_work(state.work, state.labels)


@router.patch("/works/{work_id}", operation_id="author_update_work", dependencies=[_limit_writes])
async def update_work(
    work_id: UUID, payload: WorkUpdate, author: Author, session: Session
) -> WorkResponse:
    state = await service.update_work(
        session, author=author, work_id=work_id, changes=payload.model_dump(exclude_unset=True)
    )
    return WorkResponse.from_work(state.work, state.labels)


@router.post(
    "/works/{work_id}/episodes",
    operation_id="author_create_episode",
    status_code=status.HTTP_201_CREATED,
    dependencies=[_limit_writes],
)
async def create_episode(
    work_id: UUID, payload: EpisodeCreate, author: Author, session: Session
) -> EpisodeResponse:
    state = await service.create_episode(
        session, author=author, work_id=work_id, title=payload.title
    )
    return EpisodeResponse.from_episode(state.episode, state.latest_version_id)


@router.get("/works/{work_id}/episodes", operation_id="author_list_episodes")
async def list_episodes(work_id: UUID, author: Author, session: Session) -> list[EpisodeResponse]:
    states = await service.list_episodes(session, author=author, work_id=work_id)
    return [
        EpisodeResponse.from_episode(state.episode, state.latest_version_id) for state in states
    ]


@router.get("/episodes/{episode_id}", operation_id="author_get_episode")
async def get_episode(episode_id: UUID, author: Author, session: Session) -> EpisodeResponse:
    state = await service.get_episode(session, author=author, episode_id=episode_id)
    return EpisodeResponse.from_episode(state.episode, state.latest_version_id)


@router.patch(
    "/episodes/{episode_id}", operation_id="author_update_episode", dependencies=[_limit_writes]
)
async def update_episode(
    episode_id: UUID, payload: EpisodeUpdate, author: Author, session: Session
) -> EpisodeResponse:
    state = await service.update_episode(
        session, author=author, episode_id=episode_id, title=payload.title
    )
    return EpisodeResponse.from_episode(state.episode, state.latest_version_id)


@router.put(
    "/episodes/{episode_id}/draft", operation_id="author_save_draft", dependencies=[_limit_writes]
)
async def save_draft(
    episode_id: UUID, payload: DraftSave, author: Author, session: Session
) -> EpisodeVersionSummary:
    version, episode = await service.save_draft(
        session, author=author, episode_id=episode_id, body_md=payload.body_md
    )
    return EpisodeVersionSummary.from_version(version, episode)


@router.get("/episodes/{episode_id}/draft", operation_id="author_get_draft")
async def get_draft(episode_id: UUID, author: Author, session: Session) -> EpisodeDraft:
    version = await service.get_draft(session, author=author, episode_id=episode_id)
    return EpisodeDraft.from_version(version)


@router.get("/episodes/{episode_id}/versions", operation_id="author_list_versions")
async def list_versions(
    episode_id: UUID,
    author: Author,
    session: Session,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    # The id of the last version already shown; the answer continues below it.
    before: UUID | None = None,
) -> list[EpisodeVersionSummary]:
    versions, episode = await service.list_versions(
        session, author=author, episode_id=episode_id, limit=limit, before=before
    )
    return [EpisodeVersionSummary.from_version(version, episode) for version in versions]


@router.get("/episodes/{episode_id}/versions/{version_id}", operation_id="author_get_version")
async def get_version(
    episode_id: UUID, version_id: UUID, author: Author, session: Session
) -> EpisodeVersionDetail:
    version, episode = await service.get_version(
        session, author=author, episode_id=episode_id, version_id=version_id
    )
    return EpisodeVersionDetail.from_version(version, episode)


@router.post(
    "/episodes/{episode_id}/versions/{version_id}/restore",
    operation_id="author_restore_version",
    status_code=status.HTTP_201_CREATED,
    dependencies=[_limit_writes],
)
async def restore_version(
    episode_id: UUID, version_id: UUID, author: Author, session: Session
) -> EpisodeVersionSummary:
    version, episode = await service.restore_version(
        session, author=author, episode_id=episode_id, version_id=version_id
    )
    return EpisodeVersionSummary.from_version(version, episode)


@router.post(
    "/episodes/{episode_id}/publish",
    operation_id="author_publish_episode",
    dependencies=[_limit_writes],
)
async def publish_episode(episode_id: UUID, author: Author, session: Session) -> EpisodeResponse:
    state = await service.publish_episode(session, author=author, episode_id=episode_id)
    return EpisodeResponse.from_episode(state.episode, state.latest_version_id)


@router.post(
    "/episodes/{episode_id}/schedule",
    operation_id="author_schedule_episode",
    dependencies=[_limit_writes],
)
async def schedule_episode(
    episode_id: UUID, payload: EpisodeSchedule, author: Author, session: Session
) -> EpisodeResponse:
    state = await service.schedule_episode(
        session, author=author, episode_id=episode_id, publish_at=payload.publish_at
    )
    return EpisodeResponse.from_episode(state.episode, state.latest_version_id)


@router.delete(
    "/episodes/{episode_id}/schedule",
    operation_id="author_unschedule_episode",
    dependencies=[_limit_writes],
)
async def unschedule_episode(episode_id: UUID, author: Author, session: Session) -> EpisodeResponse:
    state = await service.unschedule_episode(session, author=author, episode_id=episode_id)
    return EpisodeResponse.from_episode(state.episode, state.latest_version_id)


@router.get("/works/{work_id}/glossary", operation_id="author_list_glossary")
async def list_glossary(
    work_id: UUID, author: Author, session: Session
) -> list[GlossaryEntryResponse]:
    entries = await service.list_glossary(session, author=author, work_id=work_id)
    return [GlossaryEntryResponse.from_entry(entry) for entry in entries]


@router.post(
    "/works/{work_id}/glossary",
    operation_id="author_create_glossary_entry",
    status_code=status.HTTP_201_CREATED,
    dependencies=[_limit_writes],
)
async def create_glossary_entry(
    work_id: UUID, payload: GlossaryEntryCreate, author: Author, session: Session
) -> GlossaryEntryResponse:
    entry = await service.create_glossary_entry(
        session,
        author=author,
        work_id=work_id,
        kind=payload.kind,
        name=payload.name,
        aliases=payload.aliases,
        attributes=payload.attributes,
        translations={str(code): text for code, text in payload.translations.items()},
    )
    return GlossaryEntryResponse.from_entry(entry)


@router.patch(
    "/works/{work_id}/glossary/{entry_id}",
    operation_id="author_update_glossary_entry",
    dependencies=[_limit_writes],
)
async def update_glossary_entry(
    work_id: UUID,
    entry_id: UUID,
    payload: GlossaryEntryUpdate,
    author: Author,
    session: Session,
) -> GlossaryEntryResponse:
    entry = await service.update_glossary_entry(
        session,
        author=author,
        work_id=work_id,
        entry_id=entry_id,
        changes=payload.model_dump(exclude_unset=True),
    )
    return GlossaryEntryResponse.from_entry(entry)
