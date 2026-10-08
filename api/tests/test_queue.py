"""The enqueue side of architecture rule 4: asking for work is idempotent."""

from uuid import uuid4

import pytest
import structlog
from redis.asyncio import Redis
from redis.exceptions import ConnectionError as RedisConnectionError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.core import queue
from api.core.errors import AppError
from api.core.jobs import Job, JobStatus
from api.core.queue import enqueue, queue_name


async def test_enqueue_creates_a_queued_job(db_session: AsyncSession, redis: Redis) -> None:
    target = uuid4()

    job_id = await enqueue(db_session, kind="ping", target_id=target, content_hash="h1")

    job = await db_session.get(Job, job_id, populate_existing=True)
    assert job is not None
    assert (job.kind, job.target_id, job.content_hash) == ("ping", target, "h1")
    assert (job.status, job.attempts, job.error_code) == (JobStatus.QUEUED, 0, None)
    assert await redis.zcard(queue_name()) == 1


async def test_enqueue_is_idempotent_on_kind_target_and_hash(
    db_session: AsyncSession, redis: Redis
) -> None:
    target = uuid4()

    first = await enqueue(db_session, kind="ping", target_id=target, content_hash="h1")
    second = await enqueue(db_session, kind="ping", target_id=target, content_hash="h1")

    assert second == first
    assert (await db_session.execute(select(func.count()).select_from(Job))).scalar_one() == 1
    assert await redis.zcard(queue_name()) == 1


@pytest.mark.parametrize(
    "other", [{"kind": "index"}, {"target_id": uuid4()}, {"content_hash": "h2"}]
)
async def test_any_part_of_the_key_changing_makes_a_new_job(
    db_session: AsyncSession, redis: Redis, other: dict[str, object]
) -> None:
    key = {"kind": "ping", "target_id": uuid4(), "content_hash": "h1"}

    first = await enqueue(db_session, **key)  # type: ignore[arg-type]
    second = await enqueue(db_session, **{**key, **other})  # type: ignore[arg-type]

    assert second != first
    assert await redis.zcard(queue_name()) == 2


async def test_enqueue_records_the_current_request_id(
    db_session: AsyncSession, redis: Redis
) -> None:
    with structlog.contextvars.bound_contextvars(request_id="req-42"):
        job_id = await enqueue(db_session, kind="ping", target_id=uuid4(), content_hash="h1")

    job = await db_session.get(Job, job_id, populate_existing=True)
    assert job is not None
    assert job.request_id == "req-42"


async def test_a_queue_outage_is_a_503_and_does_not_block_the_next_attempt(
    db_session: AsyncSession, redis: Redis, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def down() -> None:
        raise RedisConnectionError("connection refused")

    target = uuid4()
    with monkeypatch.context() as outage:
        outage.setattr(queue, "get_arq_pool", down)
        with pytest.raises(AppError) as error:
            await enqueue(db_session, kind="ping", target_id=target, content_hash="h1")

    assert (error.value.status_code, error.value.code) == (503, "queue_unavailable")

    job_id = await enqueue(db_session, kind="ping", target_id=target, content_hash="h1")

    job = await db_session.get(Job, job_id, populate_existing=True)
    assert job is not None
    assert (job.status, job.error_code) == (JobStatus.QUEUED, None)
    assert await redis.zcard(queue_name()) == 1
