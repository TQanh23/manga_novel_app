"""FR-NV-02: the cron that publishes scheduled episodes, and what every cron gets.

A cron must be safe to run twice in the same minute and after a missed run.
"""

import asyncio
import json
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from api.auth.models import User
from api.author import service as author_service
from api.catalogue.models import Episode, EpisodeVersion, Work
from api.core.db import set_author_context
from worker import runtime
from worker.jobs.publish_scheduled import NAME, publish_scheduled
from worker.runtime import cron, registered_crons

Sessions = async_sessionmaker[AsyncSession]
LogLines = Callable[[], list[dict[str, Any]]]


@pytest.fixture(autouse=True)
def isolated_crons(monkeypatch: pytest.MonkeyPatch) -> None:
    """Crons a test registers disappear with it."""
    monkeypatch.setattr(runtime, "_crons", dict(runtime._crons))


def ago(**delta: float) -> datetime:
    return datetime.now(UTC) - timedelta(**delta)


async def make_episode(
    sessions: Sessions, *, status: str = "scheduled", publish_at: datetime | None = None
) -> UUID:
    """An episode of a new author with one saved version, fixed as the one to publish."""
    async with sessions() as session:
        author = User(email=f"{uuid4().hex}@example.com", password_hash="x", display_name="Author")
        session.add(author)
        await session.flush()
        work = Work(author_id=author.id, type="novel", title="Scheduled", language="ko")
        session.add(work)
        await session.flush()
        episode = Episode(work_id=work.id, author_id=author.id, number=1, title="제1화")
        session.add(episode)
        await session.flush()
        await set_author_context(session, author.id)
        version = EpisodeVersion(episode_id=episode.id, author_id=author.id, body_md="예약된 원고")
        session.add(version)
        await session.flush()
        if status != "draft":
            episode.status = status
            episode.publish_at = publish_at
            episode.published_version_id = version.id
        await session.commit()
        return episode.id


async def states(sessions: Sessions) -> dict[UUID, tuple[str, datetime | None, datetime]]:
    async with sessions() as session:
        rows = await session.execute(
            text("SELECT id, status, publish_at, updated_at FROM core.episodes")
        )
        return {row.id: (row.status, row.publish_at, row.updated_at) for row in rows}


async def versions_anyone_can_read(sessions: Sessions) -> int:
    async with sessions() as session:
        rows = await session.execute(text("SELECT count(*) FROM core.episode_versions"))
        return int(rows.scalar_one())


async def test_fr_nv_02_due_episodes_go_live_and_nothing_else_changes(
    committed_sessions: Sessions,
) -> None:
    scheduled_for = ago(seconds=30)
    due = await make_episode(committed_sessions, publish_at=scheduled_for)
    later = await make_episode(committed_sessions, publish_at=ago(hours=-1))
    draft = await make_episode(committed_sessions, status="draft")
    removed = await make_episode(committed_sessions, status="removed", publish_at=ago(days=1))
    before = await states(committed_sessions)
    assert await versions_anyone_can_read(committed_sessions) == 0

    await publish_scheduled(committed_sessions)

    after = await states(committed_sessions)
    # Live at the time it was scheduled for, not at the time the cron ran.
    assert after[due][:2] == ("published", scheduled_for)
    assert {key: after[key] for key in (later, draft, removed)} == {
        key: before[key] for key in (later, draft, removed)
    }
    # The episode became readable on its own: one version, the one that was fixed.
    assert await versions_anyone_can_read(committed_sessions) == 1


async def test_fr_nv_02_running_the_cron_twice_changes_nothing_the_second_time(
    committed_sessions: Sessions,
) -> None:
    await make_episode(committed_sessions, publish_at=ago(minutes=1))
    await make_episode(committed_sessions, publish_at=ago(minutes=2))

    await publish_scheduled(committed_sessions)
    first = await states(committed_sessions)
    await publish_scheduled(committed_sessions)
    second = await states(committed_sessions)

    assert [status for status, _, _ in first.values()] == ["published", "published"]
    # Not even updated_at moved: the second run touched no row.
    assert second == first


async def test_fr_nv_02_runs_at_the_same_moment_publish_each_episode_once(
    committed_sessions: Sessions,
) -> None:
    due = [await make_episode(committed_sessions, publish_at=ago(minutes=1)) for _ in range(5)]

    async def run() -> list[UUID]:
        async with committed_sessions() as session:
            return list(await author_service.publish_due_episodes(session))

    results = await asyncio.gather(*(run() for _ in range(4)))

    published = [episode_id for result in results for episode_id in result]
    assert sorted(published) == sorted(due)
    assert {status for status, _, _ in (await states(committed_sessions)).values()} == {"published"}


async def test_fr_nv_02_an_episode_missed_for_hours_goes_live_on_the_next_run(
    committed_sessions: Sessions,
) -> None:
    scheduled_for = ago(hours=7)
    overdue = await make_episode(committed_sessions, publish_at=scheduled_for)

    await publish_scheduled(committed_sessions)

    assert (await states(committed_sessions))[overdue][:2] == ("published", scheduled_for)


def test_fr_nv_02_the_worker_runs_the_cron_every_minute() -> None:
    from worker.settings import WorkerSettings

    (job,) = [job for job in WorkerSettings.cron_jobs if job.name == f"cron:{NAME}"]

    assert (job.month, job.day, job.weekday, job.hour, job.minute) == (None,) * 5
    assert job.second == 0
    # One run per minute however many workers are up.
    assert job.unique


async def test_every_log_line_of_a_cron_run_carries_its_name_and_one_request_id(
    committed_sessions: Sessions, log_lines: LogLines
) -> None:
    due = await make_episode(committed_sessions, publish_at=ago(minutes=1))
    (job,) = [job for job in registered_crons() if job.name == f"cron:{NAME}"]

    await job.coroutine({})

    lines = [line for line in log_lines() if line.get("job_kind") == NAME]
    (published,) = [line for line in lines if line["event"] == "scheduled_episodes_published"]
    assert (published["count"], published["episode_ids"]) == (1, [str(due)])
    assert len({line["request_id"] for line in lines}) == 1
    assert published["request_id"]
    # Ids and counts only.
    assert "예약된" not in json.dumps(log_lines(), ensure_ascii=False)


async def test_a_cron_that_fails_is_logged_without_its_message_and_does_not_raise(
    log_lines: LogLines,
) -> None:
    @cron("explode")
    async def explode(sessions: Sessions) -> None:
        raise RuntimeError("第一章の本文: an author's sentence")

    (job,) = [job for job in registered_crons() if job.name == "cron:explode"]

    await job.coroutine({})

    (failed,) = [line for line in log_lines() if line.get("event") == "cron_failed"]
    assert (failed["job_kind"], failed["error_type"]) == ("explode", "RuntimeError")
    assert "test_publish_scheduled.py" in failed["error_where"]
    # The exception message quoted content; it must not reach the logs.
    assert "本文" not in json.dumps(log_lines(), ensure_ascii=False)
