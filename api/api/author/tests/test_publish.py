"""FR-NV-01: publishing an episode shows readers its newest save."""

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth.models import Role, User
from api.catalogue.models import Episode
from api.testing import AuthHeaders, MakeEpisode, MakeUser, MakeWork


async def save(
    client: AsyncClient, headers: dict[str, str], episode: Episode, body_md: str
) -> dict[str, Any]:
    response = await client.put(
        f"/v1/author/episodes/{episode.id}/draft", json={"body_md": body_md}, headers=headers
    )
    assert response.status_code == 200, response.text
    saved: dict[str, Any] = response.json()
    return saved


@pytest.fixture
async def author(make_user: MakeUser) -> User:
    return await make_user(Role.AUTHOR)


@pytest.fixture
async def episode(author: User, make_work: MakeWork, make_episode: MakeEpisode) -> Episode:
    return await make_episode(await make_work(author))


async def test_fr_nv_01_publishing_shows_readers_the_newest_save(
    client: AsyncClient, auth_headers: AuthHeaders, author: User, episode: Episode
) -> None:
    headers = auth_headers(author)
    await save(client, headers, episode, "An earlier attempt.")
    latest = await save(client, headers, episode, "The one to publish.")
    before = datetime.now(UTC)

    response = await client.post(f"/v1/author/episodes/{episode.id}/publish", headers=headers)

    assert response.status_code == 200
    published = response.json()
    assert published["status"] == "published"
    assert published["published_version_id"] == latest["id"]
    assert published["latest_version_id"] == latest["id"]
    assert published["has_unpublished_changes"] is False
    assert before <= datetime.fromisoformat(published["publish_at"]) <= datetime.now(UTC)
    history = await client.get(f"/v1/author/episodes/{episode.id}/versions", headers=headers)
    assert [version["is_published"] for version in history.json()] == [True, False]


async def test_fr_nv_01_later_saves_stay_private_until_published_again(
    client: AsyncClient, auth_headers: AuthHeaders, author: User, episode: Episode
) -> None:
    headers = auth_headers(author)
    first = await save(client, headers, episode, "First edition.")
    published = (
        await client.post(f"/v1/author/episodes/{episode.id}/publish", headers=headers)
    ).json()

    second = await save(client, headers, episode, "Second edition.")
    editing = (await client.get(f"/v1/author/episodes/{episode.id}", headers=headers)).json()

    assert editing["status"] == "published"
    assert editing["published_version_id"] == first["id"]
    assert editing["latest_version_id"] == second["id"]
    assert editing["has_unpublished_changes"] is True

    republished = (
        await client.post(f"/v1/author/episodes/{episode.id}/publish", headers=headers)
    ).json()

    assert republished["published_version_id"] == second["id"]
    assert republished["has_unpublished_changes"] is False
    # The episode went live once; a new edition does not move that.
    assert republished["publish_at"] == published["publish_at"]


async def test_fr_nv_01_publishing_now_overrides_a_later_schedule(
    client: AsyncClient,
    auth_headers: AuthHeaders,
    make_work: MakeWork,
    make_episode: MakeEpisode,
    author: User,
) -> None:
    headers = auth_headers(author)
    next_month = datetime.now(UTC) + timedelta(days=30)
    scheduled = await make_episode(
        await make_work(author), status="scheduled", publish_at=next_month
    )
    await save(client, headers, scheduled, "Ready early.")

    response = await client.post(f"/v1/author/episodes/{scheduled.id}/publish", headers=headers)

    assert response.json()["status"] == "published"
    assert datetime.fromisoformat(response.json()["publish_at"]) <= datetime.now(UTC)


@pytest.mark.parametrize("body_md", [None, "", "  \n\t\n"])
async def test_fr_nv_01_an_episode_with_no_text_cannot_be_published(
    client: AsyncClient,
    auth_headers: AuthHeaders,
    author: User,
    episode: Episode,
    body_md: str | None,
) -> None:
    headers = auth_headers(author)
    if body_md is not None:
        await save(client, headers, episode, body_md)

    response = await client.post(f"/v1/author/episodes/{episode.id}/publish", headers=headers)

    assert (response.status_code, response.json()["error"]["code"]) == (409, "nothing_to_publish")
    state = await client.get(f"/v1/author/episodes/{episode.id}", headers=headers)
    assert (state.json()["status"], state.json()["published_version_id"]) == ("draft", None)


async def test_fr_nv_01_a_removed_episode_cannot_be_published_again(
    client: AsyncClient,
    auth_headers: AuthHeaders,
    db_session: AsyncSession,
    author: User,
    episode: Episode,
) -> None:
    headers = auth_headers(author)
    await save(client, headers, episode, "Taken down.")
    await db_session.execute(
        text("UPDATE core.episodes SET status = 'removed' WHERE id = :id"), {"id": episode.id}
    )

    response = await client.post(f"/v1/author/episodes/{episode.id}/publish", headers=headers)

    assert (response.status_code, response.json()["error"]["code"]) == (409, "episode_removed")
    state = await client.get(f"/v1/author/episodes/{episode.id}", headers=headers)
    assert state.json()["status"] == "removed"


async def test_fr_nv_01_only_the_author_of_an_episode_can_publish_it(
    client: AsyncClient,
    make_user: MakeUser,
    auth_headers: AuthHeaders,
    author: User,
    episode: Episode,
) -> None:
    await save(client, auth_headers(author), episode, "Not yet.")
    url = f"/v1/author/episodes/{episode.id}/publish"

    other_author = await client.post(url, headers=auth_headers(await make_user(Role.AUTHOR)))
    reader = await client.post(url, headers=auth_headers(await make_user()))
    admin = await client.post(url, headers=auth_headers(await make_user(Role.ADMIN)))
    signed_out = await client.post(url)

    assert (other_author.status_code, other_author.json()["error"]["code"]) == (
        404,
        "episode_not_found",
    )
    assert [reader.status_code, admin.status_code, signed_out.status_code] == [403, 403, 401]
    state = await client.get(f"/v1/author/episodes/{episode.id}", headers=auth_headers(author))
    assert state.json()["status"] == "draft"
