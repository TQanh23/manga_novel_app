from datetime import datetime
from typing import Annotated, cast
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from api.catalogue.schemas import WorkCard
from api.reader import service


class EpisodeContentResponse(BaseModel):
    """A novel episode as a reader sees it."""

    id: UUID
    work_id: UUID
    number: int
    title: str
    publish_at: datetime
    # In reading order, each one sanitized HTML block (a <p>, <h2>, <blockquote>...).
    # A reading position is an index into this list.
    paragraphs: list[str]
    # The published episodes around this one, for moving on without the list.
    previous_episode_id: UUID | None
    next_episode_id: UUID | None
    # Where the caller stopped; null for a guest or a first read. May be past the
    # end if the author has since published a shorter text.
    position: int | None

    @classmethod
    def from_content(cls, content: service.EpisodeContent) -> "EpisodeContentResponse":
        episode = content.episode
        return cls(
            id=episode.id,
            work_id=episode.work_id,
            number=episode.number,
            title=episode.title,
            # Never null here: the table's CHECK requires it of a published episode.
            publish_at=cast(datetime, episode.publish_at),
            paragraphs=content.paragraphs,
            previous_episode_id=content.previous_episode_id,
            next_episode_id=content.next_episode_id,
            position=content.position,
        )


class ProgressSave(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # Paragraph index. The upper bound only keeps nonsense out.
    position: Annotated[int, Field(ge=0, le=100_000)]


class ProgressResponse(BaseModel):
    episode_id: UUID
    position: int
    saved_at: datetime

    @classmethod
    def from_progress(cls, progress: service.SavedProgress) -> "ProgressResponse":
        return cls(
            episode_id=progress.episode_id, position=progress.position, saved_at=progress.saved_at
        )


class ReadingEntryResponse(BaseModel):
    """A work the reader is in, and the episode they read last."""

    work: WorkCard
    episode_id: UUID
    episode_number: int
    episode_title: str
    position: int
    read_at: datetime

    @classmethod
    def from_entry(cls, entry: service.ReadingEntry) -> "ReadingEntryResponse":
        return cls(
            work=WorkCard.from_work(entry.work),
            episode_id=entry.last_read.episode_id,
            episode_number=entry.last_read.episode_number,
            episode_title=entry.last_read.episode_title,
            position=entry.last_read.position,
            read_at=entry.last_read.read_at,
        )


class LibraryResponse(BaseModel):
    # Most recently read first.
    reading: list[ReadingEntryResponse]
    # Most recently added first.
    favourites: list[WorkCard]

    @classmethod
    def from_library(cls, library: service.Library) -> "LibraryResponse":
        return cls(
            reading=[ReadingEntryResponse.from_entry(entry) for entry in library.reading],
            favourites=[WorkCard.from_work(work) for work in library.favourites],
        )
