"""FR-RD-03: reading an episode. Guests read free episodes; nobody reads an unpublished one."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth.models import Role, User
from api.author import service as author_service
from api.catalogue.models import Episode, Work
from api.testing import (
    AuthHeaders,
    MakeEpisode,
    MakePublishedWork,
    MakeUser,
    MakeWork,
    PublishText,
)

SECRET = "Câu văn chưa ai được đọc 아직 아무도 읽지 못한 문장"


def content_url(episode: Episode) -> str:
    return f"/v1/episodes/{episode.id}/content"


@pytest.fixture
async def author(make_user: MakeUser) -> User:
    return await make_user(Role.AUTHOR)


@pytest.fixture
async def work(author: User, make_work: MakeWork) -> Work:
    return await make_work(author)


async def save_draft(
    client: AsyncClient, headers: dict[str, str], episode: Episode, body_md: str
) -> None:
    response = await client.put(
        f"/v1/author/episodes/{episode.id}/draft", json={"body_md": body_md}, headers=headers
    )
    assert response.status_code == 200, response.text


async def test_fr_rd_03_a_guest_reads_a_free_episode_paragraph_by_paragraph(
    client: AsyncClient, work: Work, make_episode: MakeEpisode, publish_text: PublishText
) -> None:
    episode = await make_episode(work, title="제1화: 귀환")
    await publish_text(
        episode,
        "# 귀환\n\n그날 밤, 비가 내렸다.\n\n"
        "月の下で、剣士は立ち止まった。\n\n\nĐêm ấy **trời mưa**.\n",
    )

    response = await client.get(content_url(episode))

    assert response.status_code == 200
    content = response.json()
    assert content["paragraphs"] == [
        "# 귀환",
        "그날 밤, 비가 내렸다.",
        "月の下で、剣士は立ち止まった。",
        "Đêm ấy **trời mưa**.",
    ]
    assert (content["id"], content["work_id"]) == (str(episode.id), str(work.id))
    assert (content["number"], content["title"]) == (1, "제1화: 귀환")
    assert datetime.fromisoformat(content["publish_at"]) <= datetime.now(UTC)
    assert (content["previous_episode_id"], content["next_episode_id"]) == (None, None)
    assert content["position"] is None


async def test_fr_rd_03_previous_and_next_skip_episodes_that_are_not_published(
    client: AsyncClient, work: Work, make_episode: MakeEpisode, publish_text: PublishText
) -> None:
    first = await make_episode(work)
    await make_episode(work, title="A draft in between")
    third = await make_episode(work)
    await make_episode(work, status="scheduled", publish_at=datetime.now(UTC) + timedelta(days=1))
    fifth = await make_episode(work)
    for episode in (first, third, fifth):
        await publish_text(episode, "Text.")

    contents = [
        (await client.get(content_url(episode))).json() for episode in (first, third, fifth)
    ]

    assert [(c["previous_episode_id"], c["next_episode_id"]) for c in contents] == [
        (None, str(third.id)),
        (str(first.id), str(fifth.id)),
        (str(third.id), None),
    ]


@pytest.mark.parametrize("state", ["draft", "scheduled", "removed"])
async def test_fr_rd_03_an_episode_that_is_not_published_cannot_be_read(
    client: AsyncClient,
    db_session: AsyncSession,
    auth_headers: AuthHeaders,
    make_user: MakeUser,
    make_episode: MakeEpisode,
    author: User,
    work: Work,
    state: str,
) -> None:
    episode = await make_episode(work, title="Tiêu đề bí mật")
    headers = auth_headers(author)
    await save_draft(client, headers, episode, SECRET)
    if state == "scheduled":
        scheduled = await client.post(
            f"/v1/author/episodes/{episode.id}/schedule",
            json={"publish_at": (datetime.now(UTC) + timedelta(hours=1)).isoformat()},
            headers=headers,
        )
        assert scheduled.status_code == 200
    if state == "removed":
        await client.post(f"/v1/author/episodes/{episode.id}/publish", headers=headers)
        await db_session.execute(
            text("UPDATE core.episodes SET status = 'removed' WHERE id = :id"), {"id": episode.id}
        )

    as_guest = await client.get(content_url(episode))
    as_reader = await client.get(content_url(episode), headers=auth_headers(await make_user()))
    # Not even its author reads it here: drafts are read through the author API.
    as_author = await client.get(content_url(episode), headers=headers)
    unknown = await client.get(f"/v1/episodes/{uuid4()}/content")

    for response in (as_guest, as_reader, as_author, unknown):
        assert (response.status_code, response.json()["error"]["code"]) == (
            404,
            "episode_not_found",
        )
        assert "chưa ai được đọc" not in response.text
        assert "Tiêu đề bí mật" not in response.text
    # Nothing tells a hidden episode from one that does not exist.
    assert as_guest.json()["error"]["message"] == unknown.json()["error"]["message"]


async def test_fr_rd_03_readers_keep_seeing_the_published_text_while_the_author_edits(
    client: AsyncClient,
    auth_headers: AuthHeaders,
    make_episode: MakeEpisode,
    publish_text: PublishText,
    author: User,
    work: Work,
) -> None:
    episode = await make_episode(work)
    await publish_text(episode, "The published edition.")
    await save_draft(client, auth_headers(author), episode, f"A rewrite in progress.\n\n{SECRET}")

    response = await client.get(content_url(episode))

    assert response.json()["paragraphs"] == ["The published edition."]
    assert "chưa ai được đọc" not in response.text


async def test_fr_nv_02_a_scheduled_episode_becomes_readable_when_its_time_has_come(
    client: AsyncClient,
    db_session: AsyncSession,
    auth_headers: AuthHeaders,
    make_episode: MakeEpisode,
    author: User,
    work: Work,
) -> None:
    episode = await make_episode(work)
    headers = auth_headers(author)
    publish_at = datetime.now(UTC) + timedelta(hours=1)
    await save_draft(client, headers, episode, "예약된 원고.\n\n둘째 문단.")
    await client.post(
        f"/v1/author/episodes/{episode.id}/schedule",
        json={"publish_at": publish_at.isoformat()},
        headers=headers,
    )
    await save_draft(client, headers, episode, "A change that was not scheduled.")

    before = await client.get(content_url(episode))
    await author_service.publish_due_episodes(db_session, now=publish_at)
    after = await client.get(content_url(episode))

    assert before.status_code == 404
    assert after.status_code == 200
    # The text that was scheduled, not what was saved afterwards.
    assert after.json()["paragraphs"] == ["예약된 원고.", "둘째 문단."]
    assert datetime.fromisoformat(after.json()["publish_at"]) == publish_at


async def test_fr_rd_03_a_paid_episode_is_locked_for_everyone_until_unlocks_exist(
    client: AsyncClient,
    db_session: AsyncSession,
    auth_headers: AuthHeaders,
    make_user: MakeUser,
    make_episode: MakeEpisode,
    publish_text: PublishText,
    work: Work,
) -> None:
    episode = await make_episode(work)
    await publish_text(episode, SECRET)
    await db_session.execute(
        text("UPDATE core.episodes SET price_coins = 3 WHERE id = :id"), {"id": episode.id}
    )

    as_guest = await client.get(content_url(episode))
    as_reader = await client.get(content_url(episode), headers=auth_headers(await make_user()))

    for response in (as_guest, as_reader):
        assert (response.status_code, response.json()["error"]["code"]) == (402, "episode_locked")
        assert "chưa ai được đọc" not in response.text


async def test_fr_rd_03_a_manga_episode_has_no_text_to_read(
    client: AsyncClient, make_published_work: MakePublishedWork
) -> None:
    manga = await make_published_work(type="manga")
    (episode,) = (await client.get(f"/v1/works/{manga.id}/episodes")).json()

    response = await client.get(f"/v1/episodes/{episode['id']}/content")

    assert (response.status_code, response.json()["error"]["code"]) == (409, "not_a_novel")


async def test_fr_rd_03_a_published_episode_without_text_is_not_found(
    client: AsyncClient, make_published_work: MakePublishedWork
) -> None:
    # Cannot happen through the API, which refuses to publish nothing.
    novel = await make_published_work()
    (episode,) = (await client.get(f"/v1/works/{novel.id}/episodes")).json()

    response = await client.get(f"/v1/episodes/{episode['id']}/content")

    assert (response.status_code, response.json()["error"]["code"]) == (404, "episode_not_found")


async def test_fr_rd_03_a_signed_in_reader_gets_their_own_position_with_the_text(
    client: AsyncClient,
    auth_headers: AuthHeaders,
    make_user: MakeUser,
    make_episode: MakeEpisode,
    publish_text: PublishText,
    work: Work,
) -> None:
    episode = await make_episode(work)
    await publish_text(episode, "One.\n\nTwo.\n\nThree.")
    reader, other_reader = await make_user(), await make_user()
    await client.put(
        f"/v1/progress/{episode.id}", json={"position": 2}, headers=auth_headers(reader)
    )

    mine = await client.get(content_url(episode), headers=auth_headers(reader))
    theirs = await client.get(content_url(episode), headers=auth_headers(other_reader))
    guest = await client.get(content_url(episode))

    assert [r.json()["position"] for r in (mine, theirs, guest)] == [2, None, None]
    assert mine.json()["paragraphs"] == ["One.", "Two.", "Three."]


async def test_fr_rd_03_a_token_that_is_sent_has_to_be_valid(
    client: AsyncClient, make_episode: MakeEpisode, publish_text: PublishText, work: Work
) -> None:
    episode = await make_episode(work)
    await publish_text(episode, "Text.")

    response = await client.get(
        content_url(episode), headers={"Authorization": "Bearer not-a-real-token"}
    )

    # Not read as a guest: the client learns its session has ended.
    assert response.status_code == 401


async def test_fr_rd_03_a_malformed_id_is_rejected(client: AsyncClient) -> None:
    assert (await client.get("/v1/episodes/not-a-uuid/content")).status_code == 422
