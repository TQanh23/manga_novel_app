from datetime import datetime
from enum import StrEnum
from typing import cast
from uuid import UUID

from pydantic import BaseModel

from api.catalogue.models import ContentLanguage, Episode, Tag, WorkStatus, WorkType
from api.catalogue.service import CatalogueWork


class WorkSort(StrEnum):
    # By the time of the latest published episode.
    NEWEST = "newest"
    # A stand-in until there are reads to rank by: the number of published episodes.
    POPULAR = "popular"


class AuthorSummary(BaseModel):
    id: UUID
    display_name: str


class WorkCard(BaseModel):
    """A work as the catalogue lists it."""

    id: UUID
    type: WorkType
    title: str
    synopsis: str
    language: ContentLanguage
    status: WorkStatus
    author: AuthorSummary
    # By slug; the client translates them.
    genres: list[str]
    # Published episodes only.
    episode_count: int
    last_published_at: datetime

    @classmethod
    def from_work(cls, item: CatalogueWork) -> "WorkCard":
        work = item.listed.work
        return cls(
            id=work.id,
            type=WorkType(work.type),
            title=work.title,
            synopsis=work.synopsis,
            language=ContentLanguage(work.language),
            status=WorkStatus(work.status),
            author=AuthorSummary(id=work.author_id, display_name=item.listed.author_name),
            genres=list(item.labels.genres),
            episode_count=item.listed.episode_count,
            last_published_at=item.listed.last_published_at,
        )


class WorkDetail(WorkCard):
    tags: list[str]

    @classmethod
    def from_work(cls, item: CatalogueWork) -> "WorkDetail":
        return cls(**WorkCard.from_work(item).model_dump(), tags=list(item.labels.tags))


class WorkPage(BaseModel):
    items: list[WorkCard]
    # Whether asking again with a higher offset would return more.
    has_more: bool


class EpisodeSummary(BaseModel):
    """A published episode in a work's list. Its text is not part of the catalogue."""

    id: UUID
    number: int
    title: str
    publish_at: datetime
    price_coins: int
    wuf_eligible: bool

    @classmethod
    def from_episode(cls, episode: Episode) -> "EpisodeSummary":
        return cls(
            id=episode.id,
            number=episode.number,
            title=episode.title,
            # Never null here: the table's CHECK requires it of a published episode.
            publish_at=cast(datetime, episode.publish_at),
            price_coins=episode.price_coins,
            wuf_eligible=episode.wuf_eligible,
        )


class GenreResponse(BaseModel):
    slug: str
    # The English name, for clients without a translation of the slug.
    name: str

    @classmethod
    def from_tag(cls, tag: Tag) -> "GenreResponse":
        return cls(slug=tag.slug, name=tag.name)
