from enum import StrEnum
from uuid import UUID

from sqlalchemy import CheckConstraint, Integer, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from api.core.models import Base, TimestampMixin, UUIDPrimaryKeyMixin


class JobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class Job(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One piece of background work and its state.

    The unique key is what makes jobs idempotent: the same kind of work on the
    same target with the same input is the same job, however often it is asked
    for. Rows hold metadata only, never the content the job works on.
    """

    __tablename__ = "jobs"
    __table_args__ = (
        UniqueConstraint("kind", "target_id", "content_hash"),
        CheckConstraint(
            f"status IN ({', '.join(repr(str(status)) for status in JobStatus)})", name="status"
        ),
        {"schema": "core"},
    )

    kind: Mapped[str] = mapped_column(Text)
    target_id: Mapped[UUID]
    # Hash of the input that determines the output, never of a timestamp.
    content_hash: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(
        Text, default=JobStatus.QUEUED, server_default=JobStatus.QUEUED
    )
    attempts: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    # Id of the API request that asked for the job; bound to every log line of its runs.
    request_id: Mapped[str | None] = mapped_column(Text)
    # Exception class name of the last failure. Never the message.
    error_code: Mapped[str | None] = mapped_column(Text)
