"""FR-RD-05: where a reader stopped, kept for all their devices."""

import asyncio
from datetime import datetime
from typing import Any
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from api.auth.models import Role, User
from api.catalogue.models import Episode
from api.testing import (
    TEST_PASSWORD,
    AuthHeaders,
    MakeEpisode,
    MakeUser,
    MakeWork,
    PublishText,
)


async def stored(session: AsyncSession, episode_id: Any) -> list[tuple[Any, int]]:
    rows = await session.execute(
        text("SELECT user_id, position FROM core.reading_progress WHERE episode_id = :id"),
        {"id": episode_id},
    )
    return [tuple(row) for row in rows]


async def position(client: AsyncClient, headers: dict[str, str], episode_id: Any) -> int | None:
    response = await client.get(f"/v1/episodes/{episode_id}/content", headers=headers)
    assert response.status_code == 200, response.text
    saved: int | None = response.json()["position"]
    return saved


@pytest.fixture
async def episode(
    make_user: MakeUser, make_work: MakeWork, make_episode: MakeEpisode, publish_text: PublishText
) -> Episode:
    episode = await make_episode(await make_work(await make_user(Role.AUTHOR)))
    await publish_text(episode, "\n\n".join(f"Paragraph {n}." for n in range(1, 41)))
    return episode


@pytest.fixture
async def reader(make_user: MakeUser) -> User:
    return await make_user()


async def test_fr_rd_05_a_reader_saves_their_position_and_a_later_save_replaces_it(
    client: AsyncClient,
    db_session: AsyncSession,
    auth_headers: AuthHeaders,
    episode: Episode,
    reader: User,
) -> None:
    headers = auth_headers(reader)

    first = await client.put(f"/v1/progress/{episode.id}", json={"position": 7}, headers=headers)
    second = await client.put(f"/v1/progress/{episode.id}", json={"position": 23}, headers=headers)

    assert first.status_code == 200
    assert (first.json()["episode_id"], first.json()["position"]) == (str(episode.id), 7)
    assert second.json()["position"] == 23
    assert datetime.fromisoformat(second.json()["saved_at"]) > datetime.fromisoformat(
        first.json()["saved_at"]
    )
    assert await position(client, headers, episode.id) == 23
    assert await stored(db_session, episode.id) == [(reader.id, 23)]


async def test_fr_rd_05_a_position_saved_on_one_device_shows_on_another(
    client: AsyncClient, episode: Episode, reader: User
) -> None:
    async def sign_in() -> dict[str, str]:
        tokens = await client.post(
            "/v1/auth/login", json={"email": reader.email, "password": TEST_PASSWORD}
        )
        return {"Authorization": f"Bearer {tokens.json()['access_token']}"}

    phone, browser = await sign_in(), await sign_in()

    await client.put(f"/v1/progress/{episode.id}", json={"position": 12}, headers=phone)
    seen_in_browser = await position(client, browser, episode.id)
    await client.put(f"/v1/progress/{episode.id}", json={"position": 30}, headers=browser)
    seen_on_phone = await position(client, phone, episode.id)

    assert phone != browser
    assert (seen_in_browser, seen_on_phone) == (12, 30)


async def test_fr_rd_05_readers_do_not_see_or_change_each_others_position(
    client: AsyncClient,
    db_session: AsyncSession,
    auth_headers: AuthHeaders,
    make_user: MakeUser,
    episode: Episode,
    reader: User,
) -> None:
    other = await make_user()

    await client.put(
        f"/v1/progress/{episode.id}", json={"position": 5}, headers=auth_headers(reader)
    )
    before = await position(client, auth_headers(other), episode.id)
    await client.put(
        f"/v1/progress/{episode.id}", json={"position": 39}, headers=auth_headers(other)
    )

    assert before is None
    assert await position(client, auth_headers(reader), episode.id) == 5
    assert sorted(await stored(db_session, episode.id), key=lambda row: row[1]) == [
        (reader.id, 5),
        (other.id, 39),
    ]


@pytest.mark.parametrize("value", [0, 100_000])
async def test_fr_rd_05_the_first_paragraph_and_a_far_one_are_both_valid_positions(
    client: AsyncClient, auth_headers: AuthHeaders, episode: Episode, reader: User, value: int
) -> None:
    # Not checked against the episode's length: the text may get shorter later.
    response = await client.put(
        f"/v1/progress/{episode.id}", json={"position": value}, headers=auth_headers(reader)
    )

    assert (response.status_code, response.json()["position"]) == (200, value)


@pytest.mark.parametrize(
    "payload",
    [
        {"position": -1},
        {"position": 100_001},
        {"position": "three"},
        {"position": 2.5},
        {"position": None},
        {},
        {"position": 3, "user_id": str(uuid4())},
    ],
)
async def test_fr_rd_05_an_invalid_position_is_rejected(
    client: AsyncClient,
    db_session: AsyncSession,
    auth_headers: AuthHeaders,
    episode: Episode,
    reader: User,
    payload: dict[str, Any],
) -> None:
    response = await client.put(
        f"/v1/progress/{episode.id}", json=payload, headers=auth_headers(reader)
    )

    assert (response.status_code, response.json()["error"]["code"]) == (422, "validation_error")
    assert await stored(db_session, episode.id) == []


async def test_fr_rd_05_progress_is_kept_only_for_episodes_that_can_be_read(
    client: AsyncClient,
    db_session: AsyncSession,
    auth_headers: AuthHeaders,
    make_user: MakeUser,
    make_work: MakeWork,
    make_episode: MakeEpisode,
    publish_text: PublishText,
    reader: User,
) -> None:
    work = await make_work(await make_user(Role.AUTHOR))
    draft = await make_episode(work)
    paid = await make_episode(work)
    await publish_text(paid, "Text.")
    await db_session.execute(
        text("UPDATE core.episodes SET price_coins = 3 WHERE id = :id"), {"id": paid.id}
    )
    headers = auth_headers(reader)

    responses = [
        await client.put(f"/v1/progress/{draft.id}", json={"position": 1}, headers=headers),
        await client.put(f"/v1/progress/{uuid4()}", json={"position": 1}, headers=headers),
        await client.put(f"/v1/progress/{paid.id}", json={"position": 1}, headers=headers),
    ]

    assert [(r.status_code, r.json()["error"]["code"]) for r in responses] == [
        (404, "episode_not_found"),
        (404, "episode_not_found"),
        (402, "episode_locked"),
    ]
    assert await stored(db_session, draft.id) == await stored(db_session, paid.id) == []


async def test_fr_rd_05_saving_progress_requires_sign_in(
    client: AsyncClient, db_session: AsyncSession, episode: Episode
) -> None:
    response = await client.put(f"/v1/progress/{episode.id}", json={"position": 1})

    assert response.status_code == 401
    assert await stored(db_session, episode.id) == []


async def sign_up(client: AsyncClient, email: str, *, author: bool = False) -> dict[str, str]:
    credentials = {"email": email, "password": TEST_PASSWORD}
    await client.post("/v1/auth/register", json={**credentials, "display_name": email})
    tokens = (await client.post("/v1/auth/login", json=credentials)).json()
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    if author:
        assert (await client.post("/v1/me/roles/author", headers=headers)).status_code == 200
    return headers


async def test_fr_rd_05_devices_saving_at_the_same_moment_leave_one_position(
    committing_client: AsyncClient, committed_sessions: async_sessionmaker[AsyncSession]
) -> None:
    client = committing_client
    author = await sign_up(client, "author@example.com", author=True)
    work = await client.post(
        "/v1/author/works",
        json={"type": "novel", "title": "Read by many", "language": "en"},
        headers=author,
    )
    episode = await client.post(
        f"/v1/author/works/{work.json()['id']}/episodes", json={"title": "One"}, headers=author
    )
    episode_id = episode.json()["id"]
    await client.put(
        f"/v1/author/episodes/{episode_id}/draft", json={"body_md": "Text."}, headers=author
    )
    await client.post(f"/v1/author/episodes/{episode_id}/publish", headers=author)
    reader = await sign_up(client, "reader@example.com")

    responses = await asyncio.gather(
        *(
            client.put(f"/v1/progress/{episode_id}", json={"position": n}, headers=reader)
            for n in range(20)
        )
    )

    assert [response.status_code for response in responses] == [200] * 20
    async with committed_sessions() as session:
        rows = await stored(session, episode_id)
    assert len(rows) == 1
    assert rows[0][1] in range(20)
    assert await position(client, reader, episode_id) == rows[0][1]
