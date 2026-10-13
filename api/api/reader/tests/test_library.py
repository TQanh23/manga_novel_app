"""FR-RD-05: the library: what a reader is reading and what they keep."""

from typing import Any
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth.models import Role, User
from api.catalogue.models import Work
from api.testing import AuthHeaders, MakePublishedWork, MakeUser, MakeWork


async def episode_ids(client: AsyncClient, work: Work) -> list[str]:
    episodes = (await client.get(f"/v1/works/{work.id}/episodes")).json()
    return [episode["id"] for episode in episodes]


async def read(client: AsyncClient, headers: dict[str, str], episode_id: str, at: int) -> None:
    response = await client.put(
        f"/v1/progress/{episode_id}", json={"position": at}, headers=headers
    )
    assert response.status_code == 200, response.text


async def library(client: AsyncClient, headers: dict[str, str]) -> dict[str, Any]:
    response = await client.get("/v1/library", headers=headers)
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    return body


@pytest.fixture
async def reader(make_user: MakeUser) -> User:
    return await make_user()


async def test_fr_rd_05_a_new_readers_library_is_empty(
    client: AsyncClient, auth_headers: AuthHeaders, reader: User
) -> None:
    assert await library(client, auth_headers(reader)) == {"reading": [], "favourites": []}


async def test_fr_rd_05_reading_lists_each_work_once_with_the_episode_read_last(
    client: AsyncClient,
    auth_headers: AuthHeaders,
    make_user: MakeUser,
    make_published_work: MakePublishedWork,
    reader: User,
) -> None:
    headers = auth_headers(reader)
    author = await make_user(Role.AUTHOR, display_name="김작가")
    saga = await make_published_work(author, title="달빛 아래의 검", episodes=3, genres=["fantasy"])
    other = await make_published_work(title="The Lantern Road")
    saga_episodes, other_episodes = (
        await episode_ids(client, saga),
        await episode_ids(client, other),
    )

    await read(client, headers, saga_episodes[0], at=3)
    await read(client, headers, other_episodes[0], at=1)
    await read(client, headers, saga_episodes[1], at=7)

    reading = (await library(client, headers))["reading"]

    assert [
        (entry["work"]["title"], entry["episode_number"], entry["position"]) for entry in reading
    ] == [("달빛 아래의 검", 2, 7), ("The Lantern Road", 1, 1)]
    first = reading[0]
    assert (first["episode_id"], first["episode_title"]) == (saga_episodes[1], "Episode 2")
    assert first["work"]["author"]["display_name"] == "김작가"
    assert (first["work"]["genres"], first["work"]["episode_count"]) == (["fantasy"], 3)

    # Going back to an earlier episode makes that the place to resume.
    await read(client, headers, other_episodes[0], at=4)
    await read(client, headers, saga_episodes[0], at=9)

    again = (await library(client, headers))["reading"]
    assert [
        (entry["work"]["title"], entry["episode_number"], entry["position"]) for entry in again
    ] == [
        ("달빛 아래의 검", 1, 9),
        ("The Lantern Road", 1, 4),
    ]


async def test_fr_rd_05_a_reader_keeps_and_drops_favourites(
    client: AsyncClient,
    auth_headers: AuthHeaders,
    make_published_work: MakePublishedWork,
    reader: User,
) -> None:
    headers = auth_headers(reader)
    first = await make_published_work(title="Kept first")
    second = await make_published_work(title="Kept second")

    added = [
        await client.put(f"/v1/favourites/{first.id}", headers=headers),
        await client.put(f"/v1/favourites/{second.id}", headers=headers),
        # Keeping it twice is the same as keeping it once.
        await client.put(f"/v1/favourites/{first.id}", headers=headers),
    ]
    kept = (await library(client, headers))["favourites"]
    removed = [
        await client.delete(f"/v1/favourites/{first.id}", headers=headers),
        await client.delete(f"/v1/favourites/{first.id}", headers=headers),
        await client.delete(f"/v1/favourites/{uuid4()}", headers=headers),
    ]
    left = (await library(client, headers))["favourites"]

    assert [response.status_code for response in added + removed] == [204] * 6
    assert [response.content for response in added + removed] == [b""] * 6
    # Most recently added first; adding again did not move it.
    assert [work["title"] for work in kept] == ["Kept second", "Kept first"]
    assert [work["title"] for work in left] == ["Kept second"]
    assert (await library(client, headers))["reading"] == []


async def test_fr_rd_05_a_library_holds_nothing_of_another_readers(
    client: AsyncClient,
    auth_headers: AuthHeaders,
    make_user: MakeUser,
    make_published_work: MakePublishedWork,
    reader: User,
) -> None:
    other = await make_user()
    mine = await make_published_work(title="Mine")
    theirs = await make_published_work(title="Theirs")
    await read(client, auth_headers(reader), (await episode_ids(client, mine))[0], at=2)
    await client.put(f"/v1/favourites/{mine.id}", headers=auth_headers(reader))
    await read(client, auth_headers(other), (await episode_ids(client, theirs))[0], at=5)
    await client.put(f"/v1/favourites/{theirs.id}", headers=auth_headers(other))

    # Dropping a favourite only ever drops your own.
    await client.delete(f"/v1/favourites/{theirs.id}", headers=auth_headers(reader))

    my_library = await library(client, auth_headers(reader))
    their_library = await library(client, auth_headers(other))
    assert [entry["work"]["title"] for entry in my_library["reading"]] == ["Mine"]
    assert [work["title"] for work in my_library["favourites"]] == ["Mine"]
    assert [entry["work"]["title"] for entry in their_library["reading"]] == ["Theirs"]
    assert [work["title"] for work in their_library["favourites"]] == ["Theirs"]


async def test_fr_rd_05_a_work_with_nothing_published_leaves_the_library_until_it_is_back(
    client: AsyncClient,
    db_session: AsyncSession,
    auth_headers: AuthHeaders,
    make_published_work: MakePublishedWork,
    reader: User,
) -> None:
    headers = auth_headers(reader)
    work = await make_published_work(title="Taken down", episodes=2)
    episodes = await episode_ids(client, work)
    await read(client, headers, episodes[0], at=2)
    await read(client, headers, episodes[1], at=6)
    await client.put(f"/v1/favourites/{work.id}", headers=headers)

    async def set_status(status: str, number: int | None = None) -> None:
        await db_session.execute(
            text(
                "UPDATE core.episodes SET status = :status"
                " WHERE work_id = :work_id AND (CAST(:number AS int) IS NULL OR number = :number)"
            ),
            {"status": status, "work_id": work.id, "number": number},
        )

    await set_status("removed", number=2)
    one_removed = await library(client, headers)
    await set_status("removed")
    all_removed = await library(client, headers)
    await set_status("published")
    restored = await library(client, headers)

    # With the last-read episode gone, the one read before it is where to resume.
    assert [(e["episode_number"], e["position"]) for e in one_removed["reading"]] == [(1, 2)]
    assert [work["episode_count"] for work in one_removed["favourites"]] == [1]
    assert all_removed == {"reading": [], "favourites": []}
    # Nothing was deleted: it all comes back with the work.
    assert [(e["episode_number"], e["position"]) for e in restored["reading"]] == [(2, 6)]
    assert [work["title"] for work in restored["favourites"]] == ["Taken down"]


async def test_fr_rd_05_only_a_work_in_the_catalogue_can_be_kept(
    client: AsyncClient,
    auth_headers: AuthHeaders,
    make_user: MakeUser,
    make_work: MakeWork,
    reader: User,
) -> None:
    headers = auth_headers(reader)
    unpublished = await make_work(await make_user(Role.AUTHOR))

    responses = [
        await client.put(f"/v1/favourites/{unpublished.id}", headers=headers),
        await client.put(f"/v1/favourites/{uuid4()}", headers=headers),
    ]

    assert [(r.status_code, r.json()["error"]["code"]) for r in responses] == [
        (404, "work_not_found")
    ] * 2
    assert (await library(client, headers))["favourites"] == []


async def test_fr_rd_05_the_library_and_favourites_require_sign_in(
    client: AsyncClient, make_published_work: MakePublishedWork
) -> None:
    work = await make_published_work()

    responses = [
        await client.get("/v1/library"),
        await client.put(f"/v1/favourites/{work.id}"),
        await client.delete(f"/v1/favourites/{work.id}"),
    ]

    assert [response.status_code for response in responses] == [401] * 3


async def test_fr_rd_05_an_author_reads_and_keeps_works_like_any_reader(
    client: AsyncClient,
    auth_headers: AuthHeaders,
    make_user: MakeUser,
    make_published_work: MakePublishedWork,
) -> None:
    author = await make_user(Role.READER, Role.AUTHOR)
    headers = auth_headers(author)
    someone_elses = await make_published_work(title="By another author")

    await read(client, headers, (await episode_ids(client, someone_elses))[0], at=1)
    await client.put(f"/v1/favourites/{someone_elses.id}", headers=headers)

    mine = await library(client, headers)
    assert [entry["work"]["title"] for entry in mine["reading"]] == ["By another author"]
    assert [work["title"] for work in mine["favourites"]] == ["By another author"]
