"""FR-NV-01: saving an episode's text, and its version history."""

from collections.abc import Callable
from typing import Any
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth.models import Role, User
from api.catalogue.models import Episode
from api.core.db import set_author_context
from api.testing import AuthHeaders, MakeEpisode, MakeUser, MakeWork

LogLines = Callable[[], list[dict[str, Any]]]


async def save(
    client: AsyncClient, headers: dict[str, str], episode: Episode, body_md: str
) -> dict[str, Any]:
    response = await client.put(
        f"/v1/author/episodes/{episode.id}/draft", json={"body_md": body_md}, headers=headers
    )
    assert response.status_code == 200, response.text
    saved: dict[str, Any] = response.json()
    return saved


async def stored_versions(session: AsyncSession, author: User, episode: Episode) -> list[Any]:
    await set_author_context(session, author.id)
    rows = await session.execute(
        text(
            "SELECT id, author_id, created_by, body_md FROM core.episode_versions"
            " WHERE episode_id = :episode_id ORDER BY id"
        ),
        {"episode_id": episode.id},
    )
    return list(rows)


@pytest.fixture
async def author(make_user: MakeUser) -> User:
    return await make_user(Role.AUTHOR)


@pytest.fixture
async def episode(author: User, make_work: MakeWork, make_episode: MakeEpisode) -> Episode:
    return await make_episode(await make_work(author))


async def test_fr_nv_01_saving_a_draft_adds_a_version_owned_by_the_author(
    client: AsyncClient,
    auth_headers: AuthHeaders,
    db_session: AsyncSession,
    author: User,
    episode: Episode,
) -> None:
    saved = await save(client, auth_headers(author), episode, "그날 밤, 비가 내렸다.")

    assert saved["is_published"] is False
    assert "body_md" not in saved
    rows = await stored_versions(db_session, author, episode)
    assert [(str(row.id), row.author_id, row.created_by, row.body_md) for row in rows] == [
        (saved["id"], author.id, author.id, "그날 밤, 비가 내렸다.")
    ]


async def test_fr_nv_01_saving_the_same_text_again_adds_nothing(
    client: AsyncClient,
    auth_headers: AuthHeaders,
    db_session: AsyncSession,
    author: User,
    episode: Episode,
) -> None:
    headers = auth_headers(author)

    first = await save(client, headers, episode, "Draft one.")
    again = await save(client, headers, episode, "Draft one.")
    changed = await save(client, headers, episode, "Draft one, revised.")
    back = await save(client, headers, episode, "Draft one.")

    assert again["id"] == first["id"]
    assert len({first["id"], changed["id"], back["id"]}) == 3
    assert len(await stored_versions(db_session, author, episode)) == 3


async def test_fr_nv_01_the_draft_is_the_newest_save(
    client: AsyncClient, auth_headers: AuthHeaders, author: User, episode: Episode
) -> None:
    headers = auth_headers(author)

    empty = await client.get(f"/v1/author/episodes/{episode.id}/draft", headers=headers)
    await save(client, headers, episode, "最初の下書き")
    latest = await save(client, headers, episode, "二番目の下書き\n\n改行も残る。")
    draft = await client.get(f"/v1/author/episodes/{episode.id}/draft", headers=headers)
    state = await client.get(f"/v1/author/episodes/{episode.id}", headers=headers)

    assert empty.status_code == 200
    assert empty.json() == {"version_id": None, "body_md": "", "saved_at": None}
    assert draft.json()["version_id"] == latest["id"]
    assert draft.json()["body_md"] == "二番目の下書き\n\n改行も残る。"
    assert draft.json()["saved_at"] == latest["created_at"]
    assert state.json()["latest_version_id"] == latest["id"]
    assert state.json()["has_unpublished_changes"] is True


async def test_fr_nv_01_the_history_lists_versions_newest_first_without_their_text(
    client: AsyncClient, auth_headers: AuthHeaders, author: User, episode: Episode
) -> None:
    headers = auth_headers(author)
    saved = [(await save(client, headers, episode, f"Bản nháp {n}"))["id"] for n in range(1, 6)]
    url = f"/v1/author/episodes/{episode.id}/versions"

    everything = await client.get(url, headers=headers)
    first_page = await client.get(url, params={"limit": 2}, headers=headers)
    second_page = await client.get(url, params={"limit": 2, "before": saved[3]}, headers=headers)

    assert everything.status_code == 200
    assert [version["id"] for version in everything.json()] == saved[::-1]
    assert all(
        set(version) == {"id", "created_at", "is_published"} for version in everything.json()
    )
    assert [version["id"] for version in first_page.json()] == [saved[4], saved[3]]
    assert [version["id"] for version in second_page.json()] == [saved[2], saved[1]]


@pytest.mark.parametrize("params", [{"limit": 0}, {"limit": 101}, {"before": "not-a-uuid"}])
async def test_fr_nv_01_the_history_rejects_a_bad_page_request(
    client: AsyncClient,
    auth_headers: AuthHeaders,
    author: User,
    episode: Episode,
    params: dict[str, Any],
) -> None:
    response = await client.get(
        f"/v1/author/episodes/{episode.id}/versions", params=params, headers=auth_headers(author)
    )

    assert response.status_code == 422


async def test_fr_nv_01_an_old_version_can_be_read_and_restored_as_a_new_one(
    client: AsyncClient, auth_headers: AuthHeaders, author: User, episode: Episode
) -> None:
    headers = auth_headers(author)
    old = await save(client, headers, episode, "The first telling.")
    newer = await save(client, headers, episode, "The second telling.")
    versions = f"/v1/author/episodes/{episode.id}/versions"

    read = await client.get(f"{versions}/{old['id']}", headers=headers)
    restored = await client.post(f"{versions}/{old['id']}/restore", headers=headers)
    draft = await client.get(f"/v1/author/episodes/{episode.id}/draft", headers=headers)
    history = await client.get(versions, headers=headers)

    assert read.status_code == 200
    assert read.json()["body_md"] == "The first telling."
    assert restored.status_code == 201
    assert restored.json()["id"] not in (old["id"], newer["id"])
    assert draft.json()["version_id"] == restored.json()["id"]
    assert draft.json()["body_md"] == "The first telling."
    # Nothing is lost: what was saved in between is still there.
    assert [version["id"] for version in history.json()] == [
        restored.json()["id"],
        newer["id"],
        old["id"],
    ]


async def test_fr_nv_01_a_version_belongs_to_one_episode(
    client: AsyncClient,
    auth_headers: AuthHeaders,
    make_episode: MakeEpisode,
    make_work: MakeWork,
    author: User,
    episode: Episode,
) -> None:
    headers = auth_headers(author)
    other_episode = await make_episode(await make_work(author))
    version = await save(client, headers, other_episode, "Text of another episode.")
    versions = f"/v1/author/episodes/{episode.id}/versions"

    read = await client.get(f"{versions}/{version['id']}", headers=headers)
    restored = await client.post(f"{versions}/{version['id']}/restore", headers=headers)
    unknown = await client.get(f"{versions}/{uuid4()}", headers=headers)

    for response in (read, restored, unknown):
        assert (response.status_code, response.json()["error"]["code"]) == (
            404,
            "version_not_found",
        )
    draft = await client.get(f"/v1/author/episodes/{episode.id}/draft", headers=headers)
    assert draft.json()["version_id"] is None


async def test_fr_nv_01_a_manga_episode_has_no_text_draft(
    client: AsyncClient,
    auth_headers: AuthHeaders,
    make_work: MakeWork,
    make_episode: MakeEpisode,
    author: User,
) -> None:
    headers = auth_headers(author)
    manga_episode = await make_episode(await make_work(author, type="manga"))
    base = f"/v1/author/episodes/{manga_episode.id}"

    responses = [
        await client.put(f"{base}/draft", json={"body_md": "Text"}, headers=headers),
        await client.get(f"{base}/draft", headers=headers),
        await client.get(f"{base}/versions", headers=headers),
        await client.post(f"{base}/publish", headers=headers),
    ]

    for response in responses:
        assert (response.status_code, response.json()["error"]["code"]) == (409, "not_a_novel")


async def test_fr_nv_01_a_draft_that_is_too_long_is_rejected_without_echoing_it(
    client: AsyncClient,
    auth_headers: AuthHeaders,
    db_session: AsyncSession,
    author: User,
    episode: Episode,
) -> None:
    headers = auth_headers(author)
    at_the_limit = "가" * 200_000

    accepted = await client.put(
        f"/v1/author/episodes/{episode.id}/draft", json={"body_md": at_the_limit}, headers=headers
    )
    rejected = await client.put(
        f"/v1/author/episodes/{episode.id}/draft",
        json={"body_md": at_the_limit + "나"},
        headers=headers,
    )
    unknown_field = await client.put(
        f"/v1/author/episodes/{episode.id}/draft",
        json={"body_md": "Text", "author_id": str(uuid4())},
        headers=headers,
    )

    assert accepted.status_code == 200
    assert rejected.status_code == 422
    assert "가가가" not in rejected.text
    assert unknown_field.status_code == 422
    assert len(await stored_versions(db_session, author, episode)) == 1


async def test_nfr_06_another_author_cannot_read_save_or_restore_a_draft(
    client: AsyncClient,
    make_user: MakeUser,
    auth_headers: AuthHeaders,
    db_session: AsyncSession,
    author: User,
    episode: Episode,
) -> None:
    version = await save(client, auth_headers(author), episode, "Chỉ tác giả được đọc.")
    intruder = auth_headers(await make_user(Role.AUTHOR))
    base = f"/v1/author/episodes/{episode.id}"

    responses = [
        await client.get(f"{base}/draft", headers=intruder),
        await client.put(f"{base}/draft", json={"body_md": "Overwritten"}, headers=intruder),
        await client.get(f"{base}/versions", headers=intruder),
        await client.get(f"{base}/versions/{version['id']}", headers=intruder),
        await client.post(f"{base}/versions/{version['id']}/restore", headers=intruder),
    ]

    for response in responses:
        assert (response.status_code, response.json()["error"]["code"]) == (
            404,
            "episode_not_found",
        )
        assert "Chỉ tác giả" not in response.text
    rows = await stored_versions(db_session, author, episode)
    assert [(UUID(version["id"]), "Chỉ tác giả được đọc.")] == [
        (row.id, row.body_md) for row in rows
    ]


async def test_fr_auth_03_draft_routes_are_for_authors_only(
    client: AsyncClient,
    make_user: MakeUser,
    auth_headers: AuthHeaders,
    author: User,
    episode: Episode,
) -> None:
    await save(client, auth_headers(author), episode, "Text")
    base = f"/v1/author/episodes/{episode.id}"

    for headers, expected in ((auth_headers(await make_user(Role.ADMIN)), 403), (None, 401)):
        responses = [
            await client.get(f"{base}/draft", headers=headers),
            await client.put(f"{base}/draft", json={"body_md": "X"}, headers=headers),
            await client.get(f"{base}/versions", headers=headers),
        ]

        assert [response.status_code for response in responses] == [expected] * 3


async def test_the_text_of_a_draft_never_reaches_the_logs(
    client: AsyncClient,
    auth_headers: AuthHeaders,
    log_lines: LogLines,
    author: User,
    episode: Episode,
) -> None:
    headers = auth_headers(author)
    secret = "Câu văn chưa ai được đọc 아직 아무도 읽지 못한 문장"

    saved = await save(client, headers, episode, secret)
    await client.get(f"/v1/author/episodes/{episode.id}/draft", headers=headers)
    await client.post(
        f"/v1/author/episodes/{episode.id}/versions/{saved['id']}/restore", headers=headers
    )
    await client.post(f"/v1/author/episodes/{episode.id}/publish", headers=headers)

    lines = log_lines()
    events = {line.get("event") for line in lines}
    assert {"draft_saved", "episode_published"} <= events
    assert not [line for line in lines if "chưa ai được đọc" in str(line) or "읽지" in str(line)]
