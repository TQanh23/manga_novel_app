"""FR-RD-01: guests browse the catalogue, filter it and page through it."""

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from httpx import AsyncClient

from api.auth.models import Role
from api.testing import MakePublishedWork, MakeUser


def ago(**delta: float) -> datetime:
    return datetime.now(UTC) - timedelta(**delta)


async def listed(client: AsyncClient, **params: Any) -> list[str]:
    response = await client.get("/v1/works", params=params)
    assert response.status_code == 200, response.text
    return [work["title"] for work in response.json()["items"]]


async def test_fr_rd_01_a_guest_sees_a_published_work_with_its_author_and_genres(
    client: AsyncClient, make_user: MakeUser, make_published_work: MakePublishedWork
) -> None:
    author = await make_user(Role.AUTHOR, display_name="Nguyễn Tác Giả")
    published_at = ago(hours=2)
    work = await make_published_work(
        author,
        title="Đường Đèn Lồng",
        synopsis="Người đưa thư đi về phương bắc.",
        language="vi",
        episodes=3,
        genres=["fantasy", "adventure"],
        tags=["Phiêu lưu"],
        last_published_at=published_at,
    )

    response = await client.get("/v1/works")

    assert response.status_code == 200
    assert response.json()["has_more"] is False
    (card,) = response.json()["items"]
    assert datetime.fromisoformat(card.pop("last_published_at")) == published_at
    assert card == {
        "id": str(work.id),
        "type": "novel",
        "title": "Đường Đèn Lồng",
        "synopsis": "Người đưa thư đi về phương bắc.",
        "language": "vi",
        "status": "ongoing",
        "author": {"id": str(author.id), "display_name": "Nguyễn Tác Giả"},
        "genres": ["adventure", "fantasy"],
        "episode_count": 3,
    }


async def test_fr_rd_01_the_catalogue_filters_by_type_genre_and_completion(
    client: AsyncClient, make_published_work: MakePublishedWork
) -> None:
    await make_published_work(title="Novel, romance, ongoing", genres=["romance"])
    await make_published_work(
        title="Novel, romance, completed", genres=["romance", "drama"], status="completed"
    )
    await make_published_work(title="Manga, action, ongoing", type="manga", genres=["action"])
    await make_published_work(title="Manga, no genre, completed", type="manga", status="completed")

    assert sorted(await listed(client)) == [
        "Manga, action, ongoing",
        "Manga, no genre, completed",
        "Novel, romance, completed",
        "Novel, romance, ongoing",
    ]
    assert sorted(await listed(client, type="manga")) == [
        "Manga, action, ongoing",
        "Manga, no genre, completed",
    ]
    assert sorted(await listed(client, genre="romance")) == [
        "Novel, romance, completed",
        "Novel, romance, ongoing",
    ]
    assert await listed(client, genre="drama") == ["Novel, romance, completed"]
    assert sorted(await listed(client, status="completed")) == [
        "Manga, no genre, completed",
        "Novel, romance, completed",
    ]
    assert await listed(client, type="novel", genre="romance", status="ongoing") == [
        "Novel, romance, ongoing"
    ]
    assert await listed(client, type="manga", genre="romance") == []


async def test_fr_rd_01_a_free_tag_is_not_a_genre_filter(
    client: AsyncClient, make_published_work: MakePublishedWork
) -> None:
    await make_published_work(title="Tagged", tags=["Isekai"])

    assert await listed(client, genre="isekai") == []
    assert await listed(client, genre="no-such-genre") == []


async def test_fr_rd_01_newest_puts_the_latest_published_episode_first(
    client: AsyncClient, make_published_work: MakePublishedWork
) -> None:
    await make_published_work(title="Updated last week", last_published_at=ago(days=7))
    await make_published_work(title="Updated an hour ago", last_published_at=ago(hours=1))
    await make_published_work(title="Updated yesterday", last_published_at=ago(days=1))

    assert await listed(client) == [
        "Updated an hour ago",
        "Updated yesterday",
        "Updated last week",
    ]
    assert await listed(client, sort="newest") == await listed(client)


async def test_fr_rd_01_popular_ranks_by_published_episodes_until_there_are_reads(
    client: AsyncClient, make_published_work: MakePublishedWork
) -> None:
    await make_published_work(title="Two, older", episodes=2, last_published_at=ago(days=3))
    await make_published_work(title="Five", episodes=5, last_published_at=ago(days=9))
    await make_published_work(title="Two, newer", episodes=2, last_published_at=ago(days=1))

    assert await listed(client, sort="popular") == ["Five", "Two, newer", "Two, older"]


async def test_fr_rd_01_the_catalogue_is_paged(
    client: AsyncClient, make_published_work: MakePublishedWork
) -> None:
    for number in range(1, 6):
        await make_published_work(title=f"Work {number}", last_published_at=ago(hours=number))

    first = (await client.get("/v1/works", params={"limit": 2})).json()
    second = (await client.get("/v1/works", params={"limit": 2, "offset": 2})).json()
    last = (await client.get("/v1/works", params={"limit": 2, "offset": 4})).json()
    beyond = (await client.get("/v1/works", params={"limit": 2, "offset": 6})).json()

    assert ([work["title"] for work in first["items"]], first["has_more"]) == (
        ["Work 1", "Work 2"],
        True,
    )
    assert ([work["title"] for work in second["items"]], second["has_more"]) == (
        ["Work 3", "Work 4"],
        True,
    )
    assert ([work["title"] for work in last["items"]], last["has_more"]) == (["Work 5"], False)
    assert (beyond["items"], beyond["has_more"]) == ([], False)


@pytest.mark.parametrize(
    "params",
    [
        {"type": "comic"},
        {"status": "paused"},
        {"sort": "random"},
        {"limit": 0},
        {"limit": 51},
        {"offset": -1},
    ],
)
async def test_fr_rd_01_a_bad_filter_or_page_is_rejected(
    client: AsyncClient, params: dict[str, Any]
) -> None:
    response = await client.get("/v1/works", params=params)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


async def test_fr_rd_01_the_genres_are_the_fixed_twelve(client: AsyncClient) -> None:
    response = await client.get("/v1/genres")

    assert response.status_code == 200
    assert [(genre["slug"], genre["name"]) for genre in response.json()] == [
        ("action", "Action"),
        ("adventure", "Adventure"),
        ("comedy", "Comedy"),
        ("drama", "Drama"),
        ("fantasy", "Fantasy"),
        ("historical", "Historical"),
        ("horror", "Horror"),
        ("mystery", "Mystery"),
        ("romance", "Romance"),
        ("sci-fi", "Sci-Fi"),
        ("slice-of-life", "Slice of Life"),
        ("thriller", "Thriller"),
    ]


async def test_fr_rd_01_a_tag_an_author_typed_is_not_listed_as_a_genre(
    client: AsyncClient, make_published_work: MakePublishedWork
) -> None:
    await make_published_work(tags=["Isekai", "회귀"])

    assert len((await client.get("/v1/genres")).json()) == 12
