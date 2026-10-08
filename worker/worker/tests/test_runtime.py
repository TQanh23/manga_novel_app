"""Architecture rules 4 and 6.

Jobs are idempotent on (kind, target_id, content_hash), retry at most three
times with backoff, land in the dead-letter list on final failure, and carry
the request id of the API call that asked for them into every log line.
"""

import json
from collections.abc import Callable
from typing import Any
from uuid import UUID, uuid4

import pytest
from arq import Retry
from arq.worker import Worker
from httpx import AsyncClient
from redis.asyncio import Redis
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from api.auth import service as auth_service
from api.auth.models import Role
from api.core.jobs import Job, JobStatus
from api.core.queue import dead_letter_key, enqueue, get_arq_pool, queue_name
from api.core.request_id import REQUEST_ID_HEADER
from api.core.security import create_access_token
from api.testing import TEST_PASSWORD
from worker import runtime
from worker.runtime import MAX_TRIES, JobContext, backoff_seconds, job, registered_functions

Sessions = async_sessionmaker[AsyncSession]
LogLines = Callable[[], list[dict[str, Any]]]


@pytest.fixture(autouse=True)
def isolated_registry(monkeypatch: pytest.MonkeyPatch) -> None:
    """Jobs a test registers disappear with it, and retries do not wait."""
    import worker.jobs  # noqa: F401 - the real jobs stay registered

    monkeypatch.setattr(runtime, "_registry", dict(runtime._registry))
    monkeypatch.setattr(runtime, "backoff_seconds", lambda attempt: 0)


async def run_worker() -> None:
    """Run the worker in-process until the queue is empty."""
    worker = Worker(
        functions=registered_functions(),
        redis_pool=await get_arq_pool(),
        queue_name=queue_name(),
        burst=True,
        max_tries=MAX_TRIES,
        keep_result=0,
        poll_delay=0.01,
        handle_signals=False,
    )
    await worker.main()


async def ask(sessions: Sessions, kind: str, target_id: UUID, content_hash: str = "hash-1") -> UUID:
    async with sessions() as session:
        return await enqueue(session, kind=kind, target_id=target_id, content_hash=content_hash)


async def load(sessions: Sessions, job_id: UUID) -> Job:
    async with sessions() as session:
        row = await session.get(Job, job_id)
        assert row is not None
        return row


async def count_jobs(sessions: Sessions) -> int:
    async with sessions() as session:
        return (await session.execute(select(func.count()).select_from(Job))).scalar_one()


async def test_a_job_runs_once_and_is_marked_succeeded(committed_sessions: Sessions) -> None:
    runs: list[JobContext] = []

    @job("count")
    async def count(context: JobContext) -> None:
        runs.append(context)

    target = uuid4()
    job_id = await ask(committed_sessions, "count", target)

    await run_worker()

    row = await load(committed_sessions, job_id)
    assert (row.status, row.attempts, row.error_code) == (JobStatus.SUCCEEDED, 1, None)
    assert [
        (run.job_id, run.kind, run.target_id, run.content_hash, run.attempt) for run in runs
    ] == [(job_id, "count", target, "hash-1", 1)]


async def test_asking_again_for_finished_work_does_nothing(committed_sessions: Sessions) -> None:
    runs: list[UUID] = []

    @job("count")
    async def count(context: JobContext) -> None:
        runs.append(context.job_id)

    target = uuid4()
    first = await ask(committed_sessions, "count", target)
    await run_worker()

    second = await ask(committed_sessions, "count", target)
    await run_worker()

    assert second == first
    assert runs == [first]
    assert await count_jobs(committed_sessions) == 1


async def test_a_second_delivery_of_a_finished_job_is_a_no_op(committed_sessions: Sessions) -> None:
    runs: list[UUID] = []

    @job("count")
    async def count(context: JobContext) -> None:
        runs.append(context.job_id)

    job_id = await ask(committed_sessions, "count", uuid4())
    await run_worker()
    # Queues deliver at least once: the same job can be handed over again.
    pool = await get_arq_pool()
    await pool.enqueue_job("count", str(job_id), _job_id=f"{job_id}-again")

    await run_worker()

    assert runs == [job_id]
    assert (await load(committed_sessions, job_id)).attempts == 1


async def test_asking_twice_before_the_job_runs_queues_it_once(
    committed_sessions: Sessions, redis: Redis
) -> None:
    target = uuid4()

    first = await ask(committed_sessions, "ping", target)
    second = await ask(committed_sessions, "ping", target)

    assert second == first
    assert await redis.zcard(queue_name()) == 1
    assert await count_jobs(committed_sessions) == 1


async def test_changed_input_is_a_new_job(committed_sessions: Sessions) -> None:
    runs: list[str] = []

    @job("count")
    async def count(context: JobContext) -> None:
        runs.append(context.content_hash)

    target = uuid4()
    first = await ask(committed_sessions, "count", target, "hash-1")
    second = await ask(committed_sessions, "count", target, "hash-2")

    await run_worker()

    assert first != second
    assert sorted(runs) == ["hash-1", "hash-2"]


async def test_a_failing_job_is_retried_three_times_then_dead_lettered(
    committed_sessions: Sessions, redis: Redis, log_lines: LogLines
) -> None:
    attempts: list[int] = []

    @job("explode")
    async def explode(context: JobContext) -> None:
        attempts.append(context.attempt)
        raise RuntimeError("第一章の本文: an author's sentence")

    target = uuid4()
    job_id = await ask(committed_sessions, "explode", target)

    await run_worker()

    assert attempts == [1, 2, 3, 4]
    row = await load(committed_sessions, job_id)
    assert (row.status, row.attempts, row.error_code) == (JobStatus.FAILED, 4, "RuntimeError")

    (entry,) = await redis.lrange(dead_letter_key(), 0, -1)  # type: ignore[misc]
    dead = json.loads(entry)
    assert dead.pop("failed_at")
    assert dead == {
        "job_id": str(job_id),
        "kind": "explode",
        "target_id": str(target),
        "error_code": "RuntimeError",
        "attempts": 4,
        "request_id": None,
    }

    events = [line["event"] for line in log_lines() if line.get("job_id") == str(job_id)]
    assert events.count("job_retrying") == 3
    assert events.count("job_dead_lettered") == 1
    # The exception message quoted content. It reaches neither Redis nor the logs.
    assert "本文" not in entry
    assert "本文" not in json.dumps(log_lines(), ensure_ascii=False)


async def test_a_dead_job_runs_again_when_asked_for_again(committed_sessions: Sessions) -> None:
    provider_is_up = False

    @job("flaky")
    async def flaky(context: JobContext) -> None:
        if not provider_is_up:
            raise ConnectionError

    target = uuid4()
    job_id = await ask(committed_sessions, "flaky", target)
    await run_worker()
    assert (await load(committed_sessions, job_id)).status == JobStatus.FAILED

    provider_is_up = True
    again = await ask(committed_sessions, "flaky", target)
    await run_worker()

    assert again == job_id
    row = await load(committed_sessions, job_id)
    assert (row.status, row.attempts, row.error_code) == (JobStatus.SUCCEEDED, 1, None)


async def test_a_job_that_asks_to_run_later_has_not_failed(
    committed_sessions: Sessions, redis: Redis
) -> None:
    @job("rate-limited")
    async def rate_limited(context: JobContext) -> None:
        if context.attempt == 1:
            raise Retry(defer=0)

    job_id = await ask(committed_sessions, "rate-limited", uuid4())

    await run_worker()

    row = await load(committed_sessions, job_id)
    assert (row.status, row.attempts, row.error_code) == (JobStatus.SUCCEEDED, 2, None)
    assert await redis.llen(dead_letter_key()) == 0  # type: ignore[misc]


def test_backoff_doubles_and_is_capped(monkeypatch: pytest.MonkeyPatch) -> None:
    assert [backoff_seconds(attempt) for attempt in (1, 2, 3)] == [10, 20, 40]
    assert backoff_seconds(30) == 300
    assert MAX_TRIES == 4


async def test_the_api_requests_id_is_on_every_log_line_of_the_job(
    committing_client: AsyncClient, committed_sessions: Sessions, log_lines: LogLines
) -> None:
    async with committed_sessions() as session:
        admin = await auth_service.register(
            session,
            email="admin@example.com",
            password=TEST_PASSWORD,
            display_name="Admin",
            roles=[Role.ADMIN],
        )
    token, _ = create_access_token(admin.id)

    response = await committing_client.post(
        "/v1/admin/jobs/ping",
        headers={"Authorization": f"Bearer {token}", REQUEST_ID_HEADER: "req-ping-1"},
    )
    assert response.status_code == 202
    job_id = response.json()["job_id"]

    await run_worker()

    job_lines = [line for line in log_lines() if line.get("job_id") == job_id]
    assert {line["event"] for line in job_lines} >= {"job_started", "pong", "job_succeeded"}
    assert {line["request_id"] for line in job_lines} == {"req-ping-1"}
    assert (await load(committed_sessions, UUID(job_id))).status == JobStatus.SUCCEEDED
