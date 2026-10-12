"""FR-NV-02: an author schedules an episode, and it goes live when its time comes."""

from datetime import UTC, datetime, timedelta, timezone
from typing import Any
from uuid import UUID

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth.models import Role, User
from api.author import service
from api.catalogue.models import Episode
from api.testing import AuthHeaders, MakeEpisode, MakeUser, MakeWork


def in_hours(hours: float) -> datetime:
    return datetime.now(UTC) + timedelta(hours=hours)


async def save(
    client: AsyncClient, headers: dict[str, str], episode: Episode, body_md: str
) -> dict[str, Any]:
    response = await client.put(
        f"/v1/author/episodes/{episode.id}/draft", json={"body_md": body_md}, headers=headers
    )
    assert response.status_code == 200, response.text
    saved: dict[str, Any] = response.json()
    return saved


async def schedule(
    client: AsyncClient, headers: dict[str, str], episode: Episode, publish_at: datetime
) -> dict[str, Any]:
    response = await client.post(
        f"/v1/author/episodes/{episode.id}/schedule",
        json={"publish_at": publish_at.isoformat()},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    scheduled: dict[str, Any] = response.json()
    return scheduled


async def versions_anyone_can_read(session: AsyncSession) -> set[UUID]:
    # No author named: what a reader's query could see.
    await session.execute(text("SELECT set_config('app.author_id', '', true)"))
    return set((await session.execute(text("SELECT id FROM core.episode_versions"))).scalars())


@pytest.fixture
async def author(make_user: MakeUser) -> User:
    return await make_user(Role.AUTHOR)


@pytest.fixture
async def episode(author: User, make_work: MakeWork, make_episode: MakeEpisode) -> Episode:
    return await make_episode(await make_work(author))


async def test_fr_nv_02_scheduling_sets_the_time_and_fixes_the_newest_save(
    client: AsyncClient,
    auth_headers: AuthHeaders,
    db_session: AsyncSession,
    author: User,
    episode: Episode,
) -> None:
    headers = auth_headers(author)
    await save(client, headers, episode, "An earlier attempt.")
    latest = await save(client, headers, episode, "The one to go live.")
    publish_at = in_hours(1)

    scheduled = await schedule(client, headers, episode, publish_at)

    assert scheduled["status"] == "scheduled"
    assert datetime.fromisoformat(scheduled["publish_at"]) == publish_at
    assert scheduled["published_version_id"] == latest["id"]
    assert scheduled["has_unpublished_changes"] is False
    # Fixed, not public: nobody but the author can read it before its time.
    assert await versions_anyone_can_read(db_session) == set()


async def test_fr_nv_02_a_time_keeps_its_instant_whatever_offset_it_was_sent_in(
    client: AsyncClient, auth_headers: AuthHeaders, author: User, episode: Episode
) -> None:
    headers = auth_headers(author)
    await save(client, headers, episode, "Tối mai lên sóng.")
    hanoi = timezone(timedelta(hours=7))
    publish_at = in_hours(20).astimezone(hanoi)

    scheduled = await schedule(client, headers, episode, publish_at)

    assert datetime.fromisoformat(scheduled["publish_at"]) == publish_at


async def test_fr_nv_02_saves_after_scheduling_wait_until_the_episode_is_scheduled_again(
    client: AsyncClient, auth_headers: AuthHeaders, author: User, episode: Episode
) -> None:
    headers = auth_headers(author)
    fixed = await save(client, headers, episode, "What was scheduled.")
    first_time, second_time = in_hours(1), in_hours(5)
    await schedule(client, headers, episode, first_time)

    newer = await save(client, headers, episode, "A change made afterwards.")
    waiting = (await client.get(f"/v1/author/episodes/{episode.id}", headers=headers)).json()

    assert waiting["status"] == "scheduled"
    assert waiting["published_version_id"] == fixed["id"]
    assert waiting["latest_version_id"] == newer["id"]
    assert waiting["has_unpublished_changes"] is True

    again = await schedule(client, headers, episode, second_time)

    assert again["published_version_id"] == newer["id"]
    assert again["has_unpublished_changes"] is False
    assert datetime.fromisoformat(again["publish_at"]) == second_time


async def test_fr_nv_02_calling_a_schedule_off_makes_the_episode_a_draft_again(
    client: AsyncClient, auth_headers: AuthHeaders, author: User, episode: Episode
) -> None:
    headers = auth_headers(author)
    saved = await save(client, headers, episode, "Not ready after all.")
    await schedule(client, headers, episode, in_hours(1))

    response = await client.delete(f"/v1/author/episodes/{episode.id}/schedule", headers=headers)

    assert response.status_code == 200
    draft = response.json()
    assert (draft["status"], draft["publish_at"], draft["published_version_id"]) == (
        "draft",
        None,
        None,
    )
    assert draft["latest_version_id"] == saved["id"]
    # Nothing is lost, and it can be scheduled again.
    assert (await schedule(client, headers, episode, in_hours(2)))["status"] == "scheduled"


async def test_fr_nv_02_publishing_now_takes_the_newest_save_over_the_scheduled_one(
    client: AsyncClient, auth_headers: AuthHeaders, author: User, episode: Episode
) -> None:
    headers = auth_headers(author)
    await save(client, headers, episode, "What was scheduled.")
    await schedule(client, headers, episode, in_hours(24))
    newer = await save(client, headers, episode, "Finished early.")

    published = await client.post(f"/v1/author/episodes/{episode.id}/publish", headers=headers)

    assert published.json()["status"] == "published"
    assert published.json()["published_version_id"] == newer["id"]
    assert datetime.fromisoformat(published.json()["publish_at"]) <= datetime.now(UTC)


@pytest.mark.parametrize(
    ("payload", "code"),
    [
        (
            {"publish_at": (datetime.now(UTC) - timedelta(minutes=1)).isoformat()},
            "publish_at_in_past",
        ),
        # No offset: the API cannot know which 8 pm is meant.
        ({"publish_at": "2099-01-01T20:00:00"}, "validation_error"),
        ({"publish_at": "tomorrow"}, "validation_error"),
        ({}, "validation_error"),
        ({"publish_at": "2099-01-01T20:00:00Z", "price_coins": 3}, "validation_error"),
    ],
)
async def test_fr_nv_02_a_schedule_needs_a_future_time_with_an_offset(
    client: AsyncClient,
    auth_headers: AuthHeaders,
    author: User,
    episode: Episode,
    payload: dict[str, Any],
    code: str,
) -> None:
    headers = auth_headers(author)
    await save(client, headers, episode, "Text")

    response = await client.post(
        f"/v1/author/episodes/{episode.id}/schedule", json=payload, headers=headers
    )

    assert (response.status_code, response.json()["error"]["code"]) == (422, code)
    state = await client.get(f"/v1/author/episodes/{episode.id}", headers=headers)
    assert state.json()["status"] == "draft"


@pytest.mark.parametrize("body_md", [None, "  \n"])
async def test_fr_nv_02_an_episode_with_no_text_cannot_be_scheduled(
    client: AsyncClient,
    auth_headers: AuthHeaders,
    author: User,
    episode: Episode,
    body_md: str | None,
) -> None:
    headers = auth_headers(author)
    if body_md is not None:
        await save(client, headers, episode, body_md)

    response = await client.post(
        f"/v1/author/episodes/{episode.id}/schedule",
        json={"publish_at": in_hours(1).isoformat()},
        headers=headers,
    )

    assert (response.status_code, response.json()["error"]["code"]) == (409, "nothing_to_publish")


async def test_fr_nv_02_a_published_or_removed_episode_cannot_be_scheduled(
    client: AsyncClient,
    auth_headers: AuthHeaders,
    db_session: AsyncSession,
    author: User,
    episode: Episode,
) -> None:
    headers = auth_headers(author)
    await save(client, headers, episode, "Already out.")
    await client.post(f"/v1/author/episodes/{episode.id}/publish", headers=headers)
    payload = {"publish_at": in_hours(1).isoformat()}
    url = f"/v1/author/episodes/{episode.id}/schedule"

    published = await client.post(url, json=payload, headers=headers)
    not_scheduled = await client.delete(url, headers=headers)
    await db_session.execute(
        text("UPDATE core.episodes SET status = 'removed' WHERE id = :id"), {"id": episode.id}
    )
    removed = await client.post(url, json=payload, headers=headers)

    assert (published.status_code, published.json()["error"]["code"]) == (409, "already_published")
    assert (not_scheduled.status_code, not_scheduled.json()["error"]["code"]) == (
        409,
        "not_scheduled",
    )
    assert (removed.status_code, removed.json()["error"]["code"]) == (409, "episode_removed")


async def test_fr_nv_02_a_draft_has_no_schedule_to_call_off(
    client: AsyncClient, auth_headers: AuthHeaders, author: User, episode: Episode
) -> None:
    response = await client.delete(
        f"/v1/author/episodes/{episode.id}/schedule", headers=auth_headers(author)
    )

    assert (response.status_code, response.json()["error"]["code"]) == (409, "not_scheduled")


async def test_fr_nv_02_a_manga_episode_cannot_be_scheduled_yet(
    client: AsyncClient,
    auth_headers: AuthHeaders,
    make_work: MakeWork,
    make_episode: MakeEpisode,
    author: User,
) -> None:
    headers = auth_headers(author)
    manga_episode = await make_episode(await make_work(author, type="manga"))
    url = f"/v1/author/episodes/{manga_episode.id}/schedule"

    scheduled = await client.post(
        url, json={"publish_at": in_hours(1).isoformat()}, headers=headers
    )
    called_off = await client.delete(url, headers=headers)

    for response in (scheduled, called_off):
        assert (response.status_code, response.json()["error"]["code"]) == (409, "not_a_novel")


async def test_fr_nv_02_only_the_author_of_an_episode_can_schedule_it_or_call_it_off(
    client: AsyncClient,
    make_user: MakeUser,
    auth_headers: AuthHeaders,
    author: User,
    episode: Episode,
) -> None:
    headers = auth_headers(author)
    await save(client, headers, episode, "Mine to schedule.")
    await schedule(client, headers, episode, in_hours(1))
    url = f"/v1/author/episodes/{episode.id}/schedule"
    payload = {"publish_at": in_hours(2).isoformat()}

    for other, expected in (
        (auth_headers(await make_user(Role.AUTHOR)), 404),
        (auth_headers(await make_user()), 403),
        (auth_headers(await make_user(Role.ADMIN)), 403),
        (None, 401),
    ):
        responses = [
            await client.post(url, json=payload, headers=other),
            await client.delete(url, headers=other),
        ]

        assert [response.status_code for response in responses] == [expected] * 2
    state = await client.get(f"/v1/author/episodes/{episode.id}", headers=headers)
    assert state.json()["status"] == "scheduled"


async def test_fr_nv_02_a_scheduled_episode_goes_live_when_its_time_has_come(
    client: AsyncClient,
    auth_headers: AuthHeaders,
    db_session: AsyncSession,
    author: User,
    episode: Episode,
) -> None:
    headers = auth_headers(author)
    fixed = await save(client, headers, episode, "예약된 원고")
    publish_at = in_hours(1)
    await schedule(client, headers, episode, publish_at)
    await save(client, headers, episode, "A change that was not scheduled.")

    too_early = await service.publish_due_episodes(
        db_session, now=publish_at - timedelta(seconds=1)
    )
    on_time = await service.publish_due_episodes(db_session, now=publish_at)
    again = await service.publish_due_episodes(db_session, now=publish_at + timedelta(hours=1))

    assert list(too_early) == []
    assert list(on_time) == [episode.id]
    assert list(again) == []
    live = (await client.get(f"/v1/author/episodes/{episode.id}", headers=headers)).json()
    assert live["status"] == "published"
    # It went live at the time it was scheduled for, with the text that was scheduled.
    assert datetime.fromisoformat(live["publish_at"]) == publish_at
    assert live["published_version_id"] == fixed["id"]
    assert live["has_unpublished_changes"] is True
    assert await versions_anyone_can_read(db_session) == {UUID(fixed["id"])}
