import asyncio
from uuid import UUID

import structlog
from arq import create_pool
from arq.connections import ArqRedis, RedisSettings
from redis.exceptions import RedisError
from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.config import get_settings
from api.core.errors import AppError
from api.core.ids import uuid7
from api.core.jobs import Job, JobStatus
from api.core.redis import redis_key
from api.core.request_id import get_request_id

logger = structlog.get_logger(__name__)

_pool: ArqRedis | None = None
_pool_lock = asyncio.Lock()


def queue_name() -> str:
    """The default queue: image processing, rollups, scheduled work."""
    return redis_key("arq", "queue")


def dead_letter_key() -> str:
    """Redis list of jobs that failed for good, newest first. Metadata only."""
    return redis_key("dead-letter")


async def get_arq_pool() -> ArqRedis:
    global _pool
    if _pool is None:
        async with _pool_lock:
            if _pool is None:
                _pool = await create_pool(
                    RedisSettings.from_dsn(get_settings().redis_url),
                    default_queue_name=queue_name(),
                )
    return _pool


async def close_arq_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.aclose()
        _pool = None


async def enqueue(session: AsyncSession, *, kind: str, target_id: UUID, content_hash: str) -> UUID:
    """Ask for a job to run and return its id. Commits the session.

    Idempotent on (kind, target_id, content_hash): asking again while the job
    is waiting, running or done returns the same id and queues nothing. Only a
    job that failed for good is queued again.

    Pass ids, never payloads: the worker loads what it needs.
    """
    request_id = get_request_id()
    job_id = (
        await session.execute(
            insert(Job)
            .values(
                id=uuid7(),
                kind=kind,
                target_id=target_id,
                content_hash=content_hash,
                status=JobStatus.QUEUED,
                request_id=request_id,
            )
            .on_conflict_do_nothing(index_elements=["kind", "target_id", "content_hash"])
            .returning(Job.id)
        )
    ).scalar_one_or_none()
    push = job_id is not None

    if job_id is None:
        job = (
            await session.execute(
                select(Job)
                .where(
                    Job.kind == kind,
                    Job.target_id == target_id,
                    Job.content_hash == content_hash,
                )
                .with_for_update()
                .execution_options(populate_existing=True)
            )
        ).scalar_one()
        job_id = job.id
        if job.status == JobStatus.FAILED:
            job.status = JobStatus.QUEUED
            job.attempts = 0
            job.error_code = None
            job.request_id = request_id
            push = True

    # The row is committed first so the worker can never pick up a job it
    # cannot find.
    await session.commit()
    if not push:
        return job_id

    try:
        pool = await get_arq_pool()
        await pool.enqueue_job(kind, str(job_id), _job_id=str(job_id))
    except (RedisError, OSError) as exc:
        # Left as "queued" the row would block every later attempt; "failed"
        # lets the next call queue it again.
        await session.execute(
            update(Job)
            .where(Job.id == job_id)
            .values(status=JobStatus.FAILED, error_code="enqueue_failed")
        )
        await session.commit()
        logger.error(
            "job_enqueue_failed", job_id=str(job_id), job_kind=kind, error_type=type(exc).__name__
        )
        raise AppError(
            "queue_unavailable", "The job queue is unavailable. Try again shortly.", status_code=503
        ) from None

    logger.info("job_enqueued", job_id=str(job_id), job_kind=kind)
    return job_id
