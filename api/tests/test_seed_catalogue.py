"""FR-RD-01: the sample works that give the reader's homepage and browse filters content."""

from collections.abc import Callable
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from api.catalogue.models import WorkStatus
from api.catalogue.text import sanitize_html, split_blocks
from api.core.config import Settings
from api.scripts.seed import (
    SAMPLE_NOVEL_AUTHOR,
    SampleNovel,
    catalogue_directories,
    load_sample_novel,
    seed,
    seed_catalogue_samples,
    seed_sample_novel,
)

LogLines = Callable[[], list[dict[str, Any]]]


@pytest.fixture
def samples(settings: Settings) -> list[SampleNovel]:
    return [load_sample_novel(directory) for directory in catalogue_directories()]


async def work_count(session: AsyncSession) -> int:
    count: int = (await session.execute(text("SELECT count(*) FROM core.works"))).scalar_one()
    return count


def test_the_samples_are_distinct_and_cover_every_content_language(
    samples: list[SampleNovel],
) -> None:
    titles = [sample.work.title for sample in samples]

    assert len(samples) == 6
    assert len(set(titles)) == len(titles)
    assert {sample.work.language for sample in samples} == {"vi", "en", "ko", "ja"}
    assert {sample.status for sample in samples} == {WorkStatus.ONGOING, WorkStatus.COMPLETED}


def test_each_chapter_is_already_clean_html(samples: list[SampleNovel]) -> None:
    for sample in samples:
        assert sample.episodes, sample.work.title
        for episode in sample.episodes:
            # Stored as an author's request would be: nothing for the sanitizer to drop.
            assert sanitize_html(episode.body_html) == episode.body_html.strip()
            assert len(split_blocks(episode.body_html)) >= 6


async def test_the_seed_publishes_every_sample_for_the_seeded_author(
    client: AsyncClient, db_session: AsyncSession, samples: list[SampleNovel]
) -> None:
    await seed(db_session)

    created = await seed_catalogue_samples(db_session)

    assert created == len(samples)
    rows = (
        await db_session.execute(
            text(
                "SELECT w.title, w.status, w.is_sample, w.ai_opt_in_training, u.email"
                " FROM core.works w JOIN core.users u ON u.id = w.author_id"
            )
        )
    ).all()
    by_title = {row.title: row for row in rows}
    for sample in samples:
        row = by_title[sample.work.title]
        assert (row.status, row.email) == (sample.status, SAMPLE_NOVEL_AUTHOR)
        # Written for this project, so samples; never opted in to training.
        assert (row.is_sample, row.ai_opt_in_training) == (True, False)
    listed = (await client.get("/v1/works", params={"limit": 50})).json()
    assert {card["title"] for card in listed["items"]} == set(by_title)


async def test_the_catalogue_has_the_sample_novel_and_the_samples_together(
    client: AsyncClient, db_session: AsyncSession, samples: list[SampleNovel]
) -> None:
    await seed(db_session)
    await seed_sample_novel(db_session)
    await seed_catalogue_samples(db_session)

    completed = (await client.get("/v1/works", params={"status": "completed"})).json()
    fantasy = (await client.get("/v1/works", params={"genre": "fantasy"})).json()

    assert await work_count(db_session) == len(samples) + 1
    assert {card["title"] for card in completed["items"]} == {
        sample.work.title for sample in samples if sample.status == WorkStatus.COMPLETED
    }
    assert len(fantasy["items"]) >= 3


async def test_seeding_again_adds_nothing(db_session: AsyncSession) -> None:
    await seed(db_session)
    await seed_catalogue_samples(db_session)
    before = await work_count(db_session)

    created_again = await seed_catalogue_samples(db_session)

    assert created_again == 0
    assert await work_count(db_session) == before


async def test_the_samples_are_not_seeded_outside_local(
    db_session: AsyncSession, settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    await seed(db_session)
    monkeypatch.setattr(settings, "environment", "production")

    with pytest.raises(RuntimeError, match="refusing"):
        await seed_catalogue_samples(db_session)

    assert await work_count(db_session) == 0


async def test_the_samples_need_the_seeded_author(db_session: AsyncSession) -> None:
    with pytest.raises(RuntimeError, match="accounts"):
        await seed_catalogue_samples(db_session)

    assert await work_count(db_session) == 0


async def test_seeding_logs_ids_and_never_the_text(
    db_session: AsyncSession, log_lines: LogLines, samples: list[SampleNovel]
) -> None:
    await seed(db_session)

    await seed_catalogue_samples(db_session)

    logged = str(log_lines())
    for sample in samples:
        assert sample.work.title not in logged
        assert sample.episodes[0].title not in logged
