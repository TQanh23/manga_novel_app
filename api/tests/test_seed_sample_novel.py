"""Task 1.9: the sample novel the seed publishes, and the files it is read from."""

from collections.abc import Callable
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import repository as auth_repository
from api.catalogue.text import sanitize_html, split_blocks
from api.core.config import Settings
from api.scripts.seed import (
    SAMPLE_NOVEL_AUTHOR,
    SAMPLE_NOVEL_DIRECTORY,
    SampleNovel,
    load_sample_novel,
    seed,
    seed_sample_novel,
)
from api.testing import AuthHeaders

LogLines = Callable[[], list[dict[str, Any]]]

TITLE_WITHOUT_DIACRITICS = "nguoi giu den ben suong"


@pytest.fixture
def novel(settings: Settings) -> SampleNovel:
    return load_sample_novel(settings.seed_dir / SAMPLE_NOVEL_DIRECTORY)


async def counts(session: AsyncSession) -> tuple[int, int, int, int]:
    row = await session.execute(
        text(
            "SELECT (SELECT count(*) FROM core.works), (SELECT count(*) FROM core.episodes),"
            " (SELECT count(*) FROM core.glossary_entries),"
            " (SELECT count(*) FROM core.tags WHERE kind = 'tag')"
        )
    )
    return tuple(row.one())


def test_the_sample_novel_has_five_chapters_long_enough_to_chunk(novel: SampleNovel) -> None:
    assert len(novel.episodes) == 5
    for episode in novel.episodes:
        paragraphs = split_blocks(episode.body_html)
        assert len(paragraphs) >= 8, episode.title
        # Enough text for more than one chunk when it is indexed.
        assert len(episode.body_html) >= 2_000, episode.title
        # Written as the API stores it, so what a reader gets matches the files.
        assert sanitize_html(episode.body_html) == episode.body_html.rstrip("\n"), episode.title
    assert (novel.work.language, novel.work.genres) == ("vi", ["fantasy", "mystery"])


def test_the_glossary_has_every_kind_and_each_entry_is_in_at_least_two_chapters(
    novel: SampleNovel,
) -> None:
    # A fact stated in two places is what a planted contradiction needs later.
    chapters = [episode.body_html.casefold() for episode in novel.episodes]

    for entry in novel.glossary:
        spellings = [entry.name, *entry.aliases]
        found_in = [
            number
            for number, chapter in enumerate(chapters, start=1)
            if any(spelling.casefold() in chapter for spelling in spellings)
        ]
        assert len(found_in) >= 2, (entry.name, found_in)
        assert entry.attributes, entry.name
        assert set(entry.translations) == {"en", "ko", "ja"}, entry.name
    assert {entry.kind for entry in novel.glossary} == {"character", "place", "term"}


async def test_the_seed_publishes_the_sample_novel_for_the_seeded_author(
    db_session: AsyncSession, novel: SampleNovel
) -> None:
    await seed(db_session)

    created = await seed_sample_novel(db_session)

    assert created is True
    work = (
        await db_session.execute(
            text(
                "SELECT w.id, w.title, w.type, w.language, w.is_sample, w.ai_opt_in_training,"
                " u.email FROM core.works w JOIN core.users u ON u.id = w.author_id"
            )
        )
    ).one()
    assert (work.title, work.type, work.language) == ("Người Giữ Đèn Bến Sương", "novel", "vi")
    assert work.email == SAMPLE_NOVEL_AUTHOR
    # Written for this project, so it is a sample; never opted in to training.
    assert (work.is_sample, work.ai_opt_in_training) == (True, False)
    episodes = (
        await db_session.execute(
            text(
                "SELECT number, title, status, price_coins, published_version_id IS NOT NULL"
                " FROM core.episodes ORDER BY number"
            )
        )
    ).all()
    assert [tuple(row) for row in episodes] == [
        (number, episode.title, "published", 0, True)
        for number, episode in enumerate(novel.episodes, start=1)
    ]
    kinds = await db_session.execute(
        text("SELECT kind, count(*) FROM core.glossary_entries GROUP BY kind ORDER BY kind")
    )
    assert [tuple(row) for row in kinds] == [("character", 6), ("place", 5), ("term", 3)]


async def test_a_guest_finds_the_sample_novel_without_diacritics_and_reads_it(
    client: AsyncClient, db_session: AsyncSession, novel: SampleNovel
) -> None:
    await seed(db_session)
    await seed_sample_novel(db_session)

    found = (await client.get("/v1/search", params={"q": TITLE_WITHOUT_DIACRITICS})).json()
    (card,) = found["items"]
    episodes = (await client.get(f"/v1/works/{card['id']}/episodes")).json()
    first = await client.get(f"/v1/episodes/{episodes[0]['id']}/content")
    last = await client.get(f"/v1/episodes/{episodes[4]['id']}/content")

    assert card["title"] == "Người Giữ Đèn Bến Sương"
    assert card["author"]["display_name"] == "Nguyễn Tác Giả"
    assert (card["genres"], card["episode_count"]) == (["fantasy", "mystery"], 5)
    assert [episode["title"] for episode in episodes] == [e.title for e in novel.episodes]
    assert first.status_code == 200
    assert first.json()["paragraphs"] == split_blocks(novel.episodes[0].body_html)
    assert (first.json()["previous_episode_id"], first.json()["next_episode_id"]) == (
        None,
        episodes[1]["id"],
    )
    assert last.json()["paragraphs"][-1].startswith("<p>An Nhiên mười bảy tuổi")


async def test_the_seeded_author_sees_the_glossary_through_the_api(
    client: AsyncClient, db_session: AsyncSession, auth_headers: AuthHeaders
) -> None:
    await seed(db_session)
    await seed_sample_novel(db_session)
    author = await auth_repository.get_user_by_email(db_session, SAMPLE_NOVEL_AUTHOR)
    assert author is not None
    headers = auth_headers(author)

    (work,) = (await client.get("/v1/author/works", headers=headers)).json()
    glossary = (await client.get(f"/v1/author/works/{work['id']}/glossary", headers=headers)).json()

    by_name = {entry["name"]: entry for entry in glossary}
    assert (work["is_sample"], sorted(work["tags"])) == (True, ["Bến sông", "Kỳ ảo", "Phiêu lưu"])
    assert len(glossary) == 14
    assert by_name["Lê An Nhiên"]["aliases"] == ["An Nhiên"]
    assert by_name["Lê An Nhiên"]["attributes"]["tuổi"] == 17
    assert by_name["Tháp Đèn"]["attributes"]["số bậc thang"] == 108
    assert by_name["Đèn Hồi Hương"]["translations"]["en"] == "the Homecoming Lamp"


async def test_seeding_again_adds_nothing_and_leaves_edits_alone(
    db_session: AsyncSession,
) -> None:
    await seed(db_session)
    await seed_sample_novel(db_session)
    before = await counts(db_session)
    await db_session.execute(text("UPDATE core.works SET synopsis = 'Edited by hand'"))
    await db_session.execute(
        text("UPDATE core.episodes SET title = 'Renamed by hand' WHERE number = 1")
    )

    created_again = await seed_sample_novel(db_session)

    assert created_again is False
    assert before == (1, 5, 14, 3)
    assert await counts(db_session) == before
    edited = await db_session.execute(
        text("SELECT w.synopsis, e.title FROM core.works w JOIN core.episodes e ON e.number = 1")
    )
    assert tuple(edited.one()) == ("Edited by hand", "Renamed by hand")


async def test_the_sample_novel_is_not_seeded_outside_local(
    db_session: AsyncSession, settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    await seed(db_session)
    monkeypatch.setattr(settings, "environment", "production")

    with pytest.raises(RuntimeError, match="refusing"):
        await seed_sample_novel(db_session)

    assert (await counts(db_session))[:2] == (0, 0)


async def test_the_sample_novel_needs_the_seeded_author(db_session: AsyncSession) -> None:
    with pytest.raises(RuntimeError, match="accounts"):
        await seed_sample_novel(db_session)

    assert (await counts(db_session))[:2] == (0, 0)


async def test_seeding_logs_ids_and_never_the_text_or_the_glossary(
    db_session: AsyncSession, log_lines: LogLines
) -> None:
    await seed(db_session)

    await seed_sample_novel(db_session)

    lines = log_lines()
    events = [line.get("event") for line in lines]
    assert events.count("episode_published") == 5
    assert events.count("glossary_entry_created") == 14
    logged = str(lines)
    for phrase in ("một trăm lẻ tám bậc", "Trần Bách", "Người Giữ Đèn", "la bàn đồng"):
        assert phrase not in logged
