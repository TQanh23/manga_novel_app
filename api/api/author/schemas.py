import json
from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    StringConstraints,
    field_validator,
)

from api.catalogue.labels import WorkLabels
from api.catalogue.models import (
    ContentLanguage,
    Episode,
    EpisodeStatus,
    EpisodeVersion,
    GlossaryEntry,
    GlossaryKind,
    Work,
    WorkStatus,
    WorkType,
)
from api.core.presets import ConfigPreset

# Lengths are counted in characters, so Korean, Japanese and Vietnamese text
# gets the same room as ASCII.
Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
Synopsis = Annotated[str, StringConstraints(strip_whitespace=True, max_length=5_000)]
# A genre is named by its slug; a tag is whatever the author types.
Genres = Annotated[
    list[Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=40)]],
    Field(max_length=3),
]
Tags = Annotated[
    list[Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=30)]],
    Field(max_length=10),
]
# A name in the glossary: of a character, a place or a term, or another way to write it.
GlossaryName = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)
]
Aliases = Annotated[list[GlossaryName], Field(max_length=20)]
# Whatever is known about the entry: eye colour, age, who is whose sister.
Attributes = Annotated[
    dict[
        Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=50)],
        JsonValue,
    ],
    Field(max_length=30),
]
# The name in the other content languages, keyed by language code.
Translations = dict[ContentLanguage, GlossaryName]
MAX_ATTRIBUTES_CHARS = 4_000
# Far above a long chapter, with room for markup; the bound keeps one request
# from holding megabytes. It applies before sanitizing.
BodyHtml = Annotated[str, StringConstraints(max_length=300_000)]


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
    genres: Genres = []
    tags: Tags = []


class WorkUpdate(AuthorRequest):
    """Fields left out stay as they are. The type of a work cannot change."""

    title: Title | None = None
    synopsis: Synopsis | None = None
    language: ContentLanguage | None = None
    status: WorkStatus | None = None
    # null turns wait-until-free off for the work.
    wuf_preset_id: UUID | None = None
    # A list replaces what the work had; an empty one clears it.
    genres: Genres | None = None
    tags: Tags | None = None


class EpisodeCreate(AuthorRequest):
    title: Title


class EpisodeUpdate(AuthorRequest):
    """Fields left out stay as they are. The text is saved through the draft route."""

    title: Title | None = None


class DraftSave(AuthorRequest):
    body_html: BodyHtml


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
    # Genres by slug, tags as they were typed.
    genres: list[str]
    tags: list[str]
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_work(cls, work: Work, labels: WorkLabels) -> "WorkResponse":
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
            genres=list(labels.genres),
            tags=list(labels.tags),
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
    body_html: str
    saved_at: datetime | None

    @classmethod
    def from_version(cls, version: EpisodeVersion | None) -> "EpisodeDraft":
        if version is None:
            return cls(version_id=None, body_html="", saved_at=None)
        return cls(version_id=version.id, body_html=version.body_html, saved_at=version.created_at)


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
    body_html: str

    @classmethod
    def from_version(cls, version: EpisodeVersion, episode: Episode) -> "EpisodeVersionDetail":
        return cls(
            id=version.id,
            created_at=version.created_at,
            is_published=version.id == episode.published_version_id,
            body_html=version.body_html,
        )


class WufPresetResponse(BaseModel):
    id: UUID
    # How long a reader waits for the next free episode.
    seconds: int

    @classmethod
    def from_preset(cls, preset: ConfigPreset) -> "WufPresetResponse":
        return cls(id=preset.id, seconds=preset.value)


def _bounded_attributes(attributes: dict[str, Any] | None) -> dict[str, Any] | None:
    # Counted in characters of the JSON text, whatever the script.
    if (
        attributes is not None
        and len(json.dumps(attributes, ensure_ascii=False)) > MAX_ATTRIBUTES_CHARS
    ):
        raise ValueError(f"attributes may hold at most {MAX_ATTRIBUTES_CHARS} characters of JSON")
    return attributes


class GlossaryEntryCreate(AuthorRequest):
    kind: GlossaryKind
    name: GlossaryName
    aliases: Aliases = []
    attributes: Attributes = {}
    translations: Translations = {}

    _attributes_size = field_validator("attributes")(_bounded_attributes)


class GlossaryEntryUpdate(AuthorRequest):
    """Fields left out stay as they are. A list or an object that is sent replaces the old one."""

    kind: GlossaryKind | None = None
    name: GlossaryName | None = None
    aliases: Aliases | None = None
    attributes: Attributes | None = None
    translations: Translations | None = None

    _attributes_size = field_validator("attributes")(_bounded_attributes)


class GlossaryEntryResponse(BaseModel):
    id: UUID
    work_id: UUID
    kind: GlossaryKind
    name: str
    aliases: list[str]
    attributes: dict[str, JsonValue]
    translations: dict[str, str]
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_entry(cls, entry: GlossaryEntry) -> "GlossaryEntryResponse":
        return cls(
            id=entry.id,
            work_id=entry.work_id,
            kind=GlossaryKind(entry.kind),
            name=entry.name,
            aliases=entry.aliases,
            attributes=entry.attributes,
            translations=entry.translations,
            created_at=entry.created_at,
            updated_at=entry.updated_at,
        )
