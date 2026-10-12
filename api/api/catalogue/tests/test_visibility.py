"""Readers see published episodes only.

Drafts, scheduled and removed episodes never appear in the catalogue or in
search, not even by title, and a work with nothing published does not exist as
far as a reader can tell.
"""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth.models import Role
from api.author import service as author_service
from api.catalogue.models import Work
from api.testing import MakeEpisode, MakePublishedWork, MakeUser, MakeWork

SCHEDULED_FOR = datetime.now(UTC) + timedelta(days=1)

# Titles of everything that must stay hidden. They share words with the
# public work on purpose, so a search for those words would find them.
HIDDEN_TITLES = [
    "Truyện Bí Mật Chỉ Có Nháp",
    "Chương nháp chưa ai đọc",
    "Truyện Bí Mật Đang Hẹn Giờ",
    "Chương hẹn giờ chưa lên sóng",
    "Truyện Bí Mật Đã Bị Gỡ",
    "Chương đã bị gỡ xuống",
    "Chương nháp của truyện công khai",
    "Chương hẹn giờ của truyện công khai",
]


@dataclass
class Shelf:
    draft_only: Work
    scheduled_only: Work
    removed_only: Work
    public: Work


@pytest.fixture
async def shelf(
    make_user: MakeUser,
    make_work: MakeWork,
    make_episode: MakeEpisode,
    make_published_work: MakePublishedWork,
) -> Shelf:
    author = await make_user(Role.AUTHOR, display_name="Tác Giả Kín Tiếng")
    draft_only = await make_work(author, title="Truyện Bí Mật Chỉ Có Nháp")
    await make_episode(draft_only, title="Chương nháp chưa ai đọc")
    scheduled_only = await make_work(author, title="Truyện Bí Mật Đang Hẹn Giờ")
    await make_episode(
        scheduled_only,
        title="Chương hẹn giờ chưa lên sóng",
        status="scheduled",
        publish_at=SCHEDULED_FOR,
    )
    removed_only = await make_work(author, title="Truyện Bí Mật Đã Bị Gỡ")
    await make_episode(
        removed_only,
        title="Chương đã bị gỡ xuống",
        status="removed",
        publish_at=datetime.now(UTC) - timedelta(days=30),
    )
    public = await make_published_work(author, title="Truyện Công Khai", episodes=2)
    await make_episode(public, title="Chương nháp của truyện công khai")
    await make_episode(
        public,
        title="Chương hẹn giờ của truyện công khai",
        status="scheduled",
        publish_at=SCHEDULED_FOR,
    )
    return Shelf(draft_only, scheduled_only, removed_only, public)


async def everything_a_reader_can_ask(client: AsyncClient, shelf: Shelf) -> list[str]:
    """The body of every catalogue answer, for every work and a search for each hidden word."""
    urls = ["/v1/works", "/v1/works?sort=popular", "/v1/works?type=novel", "/v1/genres"]
    for work in (shelf.draft_only, shelf.scheduled_only, shelf.removed_only, shelf.public):
        urls += [f"/v1/works/{work.id}", f"/v1/works/{work.id}/episodes"]
    bodies = [(await client.get(url)).text for url in urls]
    for query in ("truyen", "bi mat", "chuong", "nhap", "hen gio", "kin tieng", "go xuong"):
        bodies.append((await client.get("/v1/search", params={"q": query})).text)
    return bodies


async def test_only_a_work_with_a_published_episode_is_in_the_catalogue(
    client: AsyncClient, shelf: Shelf
) -> None:
    listed = (await client.get("/v1/works")).json()["items"]
    by_author = (await client.get("/v1/search", params={"q": "kin tieng"})).json()["items"]
    by_title = (await client.get("/v1/search", params={"q": "truyen bi mat"})).json()["items"]

    assert [work["id"] for work in listed] == [str(shelf.public.id)]
    assert [work["id"] for work in by_author] == [str(shelf.public.id)]
    assert by_title == []
    assert listed[0]["episode_count"] == 2


@pytest.mark.parametrize("hidden", ["draft_only", "scheduled_only", "removed_only"])
async def test_a_work_with_nothing_published_has_no_page(
    client: AsyncClient, shelf: Shelf, hidden: str
) -> None:
    work: Work = getattr(shelf, hidden)

    page = await client.get(f"/v1/works/{work.id}")
    episodes = await client.get(f"/v1/works/{work.id}/episodes")

    assert (page.status_code, episodes.status_code) == (404, 404)


async def test_a_public_work_lists_its_published_episodes_and_no_others(
    client: AsyncClient, shelf: Shelf
) -> None:
    page = (await client.get(f"/v1/works/{shelf.public.id}")).json()
    episodes = (await client.get(f"/v1/works/{shelf.public.id}/episodes")).json()

    assert page["episode_count"] == 2
    assert [(episode["number"], episode["title"]) for episode in episodes] == [
        (1, "Episode 1"),
        (2, "Episode 2"),
    ]


async def test_no_catalogue_answer_names_an_unpublished_work_or_episode(
    client: AsyncClient, shelf: Shelf
) -> None:
    bodies = await everything_a_reader_can_ask(client, shelf)

    assert any("Truyện Công Khai" in body for body in bodies)
    for title in HIDDEN_TITLES:
        assert not [body for body in bodies if title in body], title


async def test_fr_nv_02_a_scheduled_episode_shows_up_once_its_time_has_come(
    client: AsyncClient, db_session: AsyncSession, shelf: Shelf
) -> None:
    await author_service.publish_due_episodes(db_session, now=SCHEDULED_FOR + timedelta(seconds=1))

    listed = {work["id"]: work for work in (await client.get("/v1/works")).json()["items"]}
    episodes = (await client.get(f"/v1/works/{shelf.public.id}/episodes")).json()

    assert set(listed) == {str(shelf.public.id), str(shelf.scheduled_only.id)}
    assert listed[str(shelf.public.id)]["episode_count"] == 3
    assert [episode["title"] for episode in episodes] == [
        "Episode 1",
        "Episode 2",
        "Chương hẹn giờ của truyện công khai",
    ]
    # The drafts are as hidden as before.
    bodies = await everything_a_reader_can_ask(client, shelf)
    for title in ("Chương nháp chưa ai đọc", "Chương nháp của truyện công khai"):
        assert not [body for body in bodies if title in body], title


async def test_a_work_leaves_the_catalogue_when_its_last_published_episode_is_removed(
    client: AsyncClient, db_session: AsyncSession, shelf: Shelf
) -> None:
    await db_session.execute(
        text("UPDATE core.episodes SET status = 'removed' WHERE work_id = :id AND number = 1"),
        {"id": shelf.public.id},
    )
    still_listed = (await client.get("/v1/works")).json()["items"]
    one_left = (await client.get(f"/v1/works/{shelf.public.id}/episodes")).json()

    await db_session.execute(
        text("UPDATE core.episodes SET status = 'removed' WHERE work_id = :id AND number = 2"),
        {"id": shelf.public.id},
    )
    gone = (await client.get("/v1/works")).json()["items"]
    page = await client.get(f"/v1/works/{shelf.public.id}")

    assert [work["episode_count"] for work in still_listed] == [1]
    assert [episode["number"] for episode in one_left] == [2]
    assert gone == []
    assert page.status_code == 404
