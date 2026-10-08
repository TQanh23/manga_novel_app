"""What every job gets for free: idempotency, retries, the dead-letter list, request ids.

Write a job as a plain coroutine and register it with @job. Do not call arq or
touch core.jobs from a job directly.
"""

import json
import traceback
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import structlog
from arq import Retry
from arq.worker import Function, func
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from api.core.db import get_sessionmaker
from api.core.jobs import Job, JobStatus
from api.core.queue import dead_letter_key

logger = structlog.get_logger(__name__)

MAX_RETRIES = 3
# arq counts the first run as a try.
MAX_TRIES = MAX_RETRIES + 1
_BACKOFF_BASE_SECONDS = 5
_BACKOFF_CAP_SECONDS = 300


@dataclass(frozen=True)
class JobContext:
    """What a job is told: which work to do, never the content itself."""

    job_id: UUID
    kind: str
    target_id: UUID
    content_hash: str
    attempt: int
    # Each job opens its own sessions; nothing is shared with the bookkeeping here.
    sessions: async_sessionmaker[AsyncSession]


JobHandler = Callable[[JobContext], Awaitable[None]]

_registry: dict[str, Function] = {}


def registered_functions() -> list[Function]:
    return list(_registry.values())


def backoff_seconds(attempt: int) -> int:
    """Delay before the retry that follows the given attempt: 10 s, 20 s, 40 s."""
    return min(_BACKOFF_BASE_SECONDS << attempt, _BACKOFF_CAP_SECONDS)


def _where(exc: BaseException) -> str:
    # Where it failed, without the exception message: messages can quote the
    # content a job was working on.
    frames = traceback.extract_tb(exc.__traceback__)
    return f"{frames[-1].filename}:{frames[-1].lineno}" if frames else "unknown"


def job(kind: str) -> Callable[[JobHandler], JobHandler]:
    """Register a coroutine as the job for a kind."""

    def decorator(handler: JobHandler) -> JobHandler:
        async def run(ctx: dict[str, Any], job_id: str) -> None:
            await _run(handler, kind, ctx, UUID(job_id))

        _registry[kind] = func(run, name=kind)
        return handler

    return decorator


async def _run(handler: JobHandler, kind: str, ctx: dict[str, Any], job_id: UUID) -> None:
    sessions = get_sessionmaker()
    attempt: int = ctx["job_try"]

    async with sessions() as session:
        row = await session.get(Job, job_id)
        if row is None:
            logger.error("job_row_missing", job_id=str(job_id), job_kind=kind)
            return

        with structlog.contextvars.bound_contextvars(
            request_id=row.request_id, job_id=str(job_id), job_kind=kind
        ):
            if row.status == JobStatus.SUCCEEDED:
                # Same kind, target and input as a finished job: nothing to do.
                logger.info("job_skipped_already_done")
                return

            row.status = JobStatus.RUNNING
            row.attempts = attempt
            await session.commit()
            logger.info("job_started", attempt=attempt)

            try:
                await handler(
                    JobContext(
                        job_id=job_id,
                        kind=kind,
                        target_id=row.target_id,
                        content_hash=row.content_hash,
                        attempt=attempt,
                        sessions=sessions,
                    )
                )
            except Retry:
                # The job asked to be run later (a provider's rate limit). That
                # is not a failure of the job.
                row.status = JobStatus.QUEUED
                await session.commit()
                logger.info("job_deferred", attempt=attempt)
                raise
            except Exception as exc:
                error_code = type(exc).__name__
                row.error_code = error_code

                if attempt >= MAX_TRIES:
                    row.status = JobStatus.FAILED
                    await session.commit()
                    await ctx["redis"].lpush(
                        dead_letter_key(),
                        json.dumps(
                            {
                                "job_id": str(job_id),
                                "kind": kind,
                                "target_id": str(row.target_id),
                                "error_code": error_code,
                                "attempts": attempt,
                                "request_id": row.request_id,
                                "failed_at": datetime.now(UTC).isoformat(),
                            }
                        ),
                    )
                    logger.error(
                        "job_dead_lettered",
                        attempt=attempt,
                        error_type=error_code,
                        error_where=_where(exc),
                    )
                    return

                row.status = JobStatus.QUEUED
                await session.commit()
                delay = backoff_seconds(attempt)
                logger.warning(
                    "job_retrying",
                    attempt=attempt,
                    retry_in_seconds=delay,
                    error_type=error_code,
                    error_where=_where(exc),
                )
                raise Retry(defer=delay) from None

            row.status = JobStatus.SUCCEEDED
            row.error_code = None
            await session.commit()
            logger.info("job_succeeded", attempt=attempt)
