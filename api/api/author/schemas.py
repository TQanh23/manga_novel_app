from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, StringConstraints

from api.catalogue.models import (
    ContentLanguage,
    Episode,
    EpisodeStatus,
    EpisodeVersion,
    Work,
    WorkStatus,
    WorkType,
)
from api.core.presets import ConfigPreset

# Lengths are counted in characters, so Korean, Japanese and Vietnamese text
# gets the same room as ASCII.
Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
Synopsis = Annotated[str, StringConstraints(strip_whitespace=True, max_length=5_000)]
# Far above a long chapter; the bound keeps one request from holding megabytes.
BodyMd = Annotated[str, StringConstraints(max_length=200_000)]


class AuthorRequest(BaseModel):
    """Base of what an author sends.

    Unknown fields are refused rather than dropped, so a request that tries to
    set what authors may not (is_sample, ai_opt_in_training, the revenue split,
    a price) fails loudly instead of appearing to work.
    """

    model_config = ConfigDict(extra="forbid")


class WorkCreate(AuthorRequest):
    type: WorkType
    title: Title
    synopsis: Synopsis = ""
    language: ContentLanguage
    wuf_preset_id: UUID | None = None


class WorkUpdate(AuthorRequest):
    """Fields left out stay as they are. The type of a work cannot change."""

    title: Title | None = None
    synopsis: Synopsis | None = None
    language: ContentLanguage | None = None
    status: WorkStatus | None = None
    # null turns wait-until-free off for the work.
    wuf_preset_id: UUID | None = None


class EpisodeCreate(AuthorRequest):
    title: Title


class DraftSave(AuthorRequest):
    body_md: BodyMd


class EpisodeSchedule(AuthorRequest):
    # With an offset: "8 pm" means nothing without knowing where.
    publish_at: AwareDatetime


class WorkResponse(BaseModel):
    id: UUID
    type: WorkType
    title: str
    synopsis: str
    language: ContentLanguage
    status: WorkStatus
    wuf_preset_id: UUID | None
    revenue_share_preset_id: UUID | None
    is_sample: bool
    ai_opt_in_training: bool
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_work(cls, work: Work) -> "WorkResponse":
        return cls(
            id=work.id,
            type=WorkType(work.type),
            title=work.title,
            synopsis=work.synopsis,
            language=ContentLanguage(work.language),
            status=WorkStatus(work.status),
            wuf_preset_id=work.wuf_preset_id,
            revenue_share_preset_id=work.revenue_share_preset_id,
            is_sample=work.is_sample,
            ai_opt_in_training=work.ai_opt_in_training,
            created_at=work.created_at,
            updated_at=work.updated_at,
        )


class EpisodeResponse(BaseModel):
    id: UUID
    work_id: UUID
    number: int
    title: str
    status: EpisodeStatus
    publish_at: datetime | None
    price_coins: int
    wuf_eligible: bool
    # What readers see (or will see, while the episode is scheduled), and the
    # newest save. They differ while the author has saved changes that are not
    # published yet.
    published_version_id: UUID | None
    latest_version_id: UUID | None
    has_unpublished_changes: bool
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_episode(cls, episode: Episode, latest_version_id: UUID | None) -> "EpisodeResponse":
        return cls(
            id=episode.id,
            work_id=episode.work_id,
            number=episode.number,
            title=episode.title,
            status=EpisodeStatus(episode.status),
            publish_at=episode.publish_at,
            price_coins=episode.price_coins,
            wuf_eligible=episode.wuf_eligible,
            published_version_id=episode.published_version_id,
            latest_version_id=latest_version_id,
            has_unpublished_changes=latest_version_id != episode.published_version_id,
            created_at=episode.created_at,
            updated_at=episode.updated_at,
        )


class EpisodeDraft(BaseModel):
    """The newest save of an episode. All empty when nothing was saved yet."""

    version_id: UUID | None
    body_md: str
    saved_at: datetime | None

    @classmethod
    def from_version(cls, version: EpisodeVersion | None) -> "EpisodeDraft":
        if version is None:
            return cls(version_id=None, body_md="", saved_at=None)
        return cls(version_id=version.id, body_md=version.body_md, saved_at=version.created_at)


class EpisodeVersionSummary(BaseModel):
    """One entry of the version history, without the text."""

    id: UUID
    created_at: datetime
    is_published: bool

    @classmethod
    def from_version(cls, version: EpisodeVersion, episode: Episode) -> "EpisodeVersionSummary":
        return cls(
            id=version.id,
            created_at=version.created_at,
            is_published=version.id == episode.published_version_id,
        )


class EpisodeVersionDetail(EpisodeVersionSummary):
    body_md: str

    @classmethod
    def from_version(cls, version: EpisodeVersion, episode: Episode) -> "EpisodeVersionDetail":
        return cls(
            id=version.id,
            created_at=version.created_at,
            is_published=version.id == episode.published_version_id,
            body_md=version.body_md,
        )


class WufPresetResponse(BaseModel):
    id: UUID
    # How long a reader waits for the next free episode.
    seconds: int

    @classmethod
    def from_preset(cls, preset: ConfigPreset) -> "WufPresetResponse":
        return cls(id=preset.id, seconds=preset.value)
