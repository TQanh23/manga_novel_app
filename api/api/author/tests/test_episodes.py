"""FR-NV-01: an author adds episodes to their works."""

from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth.models import Role
from api.testing import AuthHeaders, MakeEpisode, MakeUser, MakeWork, PublishText


async def test_fr_nv_01_a_new_episode_is_a_free_draft_with_nothing_saved(
    client: AsyncClient, make_user: MakeUser, make_work: MakeWork, auth_headers: AuthHeaders
) -> None:
    author = await make_user(Role.AUTHOR)
    work = await make_work(author)

    response = await client.post(
        f"/v1/author/works/{work.id}/episodes",
        json={"title": "제1화: 귀환"},
        headers=auth_headers(author),
    )

    assert response.status_code == 201
    episode = response.json()
    assert episode["work_id"] == str(work.id)
    assert (episode["number"], episode["title"]) == (1, "제1화: 귀환")
    assert (episode["status"], episode["price_coins"], episode["wuf_eligible"]) == (
        "draft",
        0,
        False,
    )
    assert episode["publish_at"] is None
    assert episode["published_version_id"] is None
    assert episode["latest_version_id"] is None
    assert episode["has_unpublished_changes"] is False


async def test_fr_nv_01_episodes_are_numbered_in_order_within_each_work(
    client: AsyncClient, make_user: MakeUser, make_work: MakeWork, auth_headers: AuthHeaders
) -> None:
    author = await make_user(Role.AUTHOR)
    headers = auth_headers(author)
    work, other_work = await make_work(author), await make_work(author)

    numbers = [
        (
            await client.post(
                f"/v1/author/works/{work.id}/episodes", json={"title": title}, headers=headers
            )
        ).json()["number"]
        for title in ("One", "Two", "Three")
    ]
    elsewhere = await client.post(
        f"/v1/author/works/{other_work.id}/episodes", json={"title": "One"}, headers=headers
    )
    listed = await client.get(f"/v1/author/works/{work.id}/episodes", headers=headers)

    assert numbers == [1, 2, 3]
    assert elsewhere.json()["number"] == 1
    assert [(episode["number"], episode["title"]) for episode in listed.json()] == [
        (1, "One"),
        (2, "Two"),
        (3, "Three"),
    ]


async def test_fr_nv_01_an_author_reads_one_episode(
    client: AsyncClient,
    make_user: MakeUser,
    make_work: MakeWork,
    make_episode: MakeEpisode,
    auth_headers: AuthHeaders,
) -> None:
    author = await make_user(Role.AUTHOR)
    episode = await make_episode(await make_work(author), title="Chương 1")

    response = await client.get(f"/v1/author/episodes/{episode.id}", headers=auth_headers(author))

    assert response.status_code == 200
    assert (response.json()["id"], response.json()["title"]) == (str(episode.id), "Chương 1")


async def test_fr_nv_01_a_manga_work_has_episodes_too(
    client: AsyncClient, make_user: MakeUser, make_work: MakeWork, auth_headers: AuthHeaders
) -> None:
    author = await make_user(Role.AUTHOR)
    work = await make_work(author, type="manga")

    response = await client.post(
        f"/v1/author/works/{work.id}/episodes",
        json={"title": "第1話"},
        headers=auth_headers(author),
    )

    assert response.status_code == 201


@pytest.mark.parametrize("payload", [{}, {"title": " "}, {"title": "One", "price_coins": 0}])
async def test_fr_nv_01_invalid_episodes_are_rejected(
    client: AsyncClient,
    make_user: MakeUser,
    make_work: MakeWork,
    auth_headers: AuthHeaders,
    payload: dict[str, object],
) -> None:
    author = await make_user(Role.AUTHOR)
    work = await make_work(author)

    response = await client.post(
        f"/v1/author/works/{work.id}/episodes", json=payload, headers=auth_headers(author)
    )

    assert response.status_code == 422
    listed = await client.get(f"/v1/author/works/{work.id}/episodes", headers=auth_headers(author))
    assert listed.json() == []


async def test_fr_nv_01_an_author_cannot_add_to_list_or_read_another_authors_episodes(
    client: AsyncClient,
    make_user: MakeUser,
    make_work: MakeWork,
    make_episode: MakeEpisode,
    auth_headers: AuthHeaders,
) -> None:
    author, other_author = await make_user(Role.AUTHOR), await make_user(Role.AUTHOR)
    work = await make_work(author)
    episode = await make_episode(work)
    headers = auth_headers(other_author)

    added = await client.post(
        f"/v1/author/works/{work.id}/episodes", json={"title": "Uninvited"}, headers=headers
    )
    listed = await client.get(f"/v1/author/works/{work.id}/episodes", headers=headers)
    fetched = await client.get(f"/v1/author/episodes/{episode.id}", headers=headers)
    missing = await client.get(f"/v1/author/episodes/{uuid4()}", headers=headers)

    assert (added.status_code, added.json()["error"]["code"]) == (404, "work_not_found")
    assert (listed.status_code, listed.json()["error"]["code"]) == (404, "work_not_found")
    assert (fetched.status_code, fetched.json()["error"]["code"]) == (404, "episode_not_found")
    assert missing.status_code == 404
    mine = await client.get(f"/v1/author/works/{work.id}/episodes", headers=auth_headers(author))
    assert [item["id"] for item in mine.json()] == [str(episode.id)]


async def test_fr_auth_03_episode_routes_are_for_authors_only(
    client: AsyncClient,
    make_user: MakeUser,
    make_work: MakeWork,
    make_episode: MakeEpisode,
    auth_headers: AuthHeaders,
) -> None:
    work = await make_work(await make_user(Role.AUTHOR))
    episode = await make_episode(work)
    reader = auth_headers(await make_user())

    as_reader = [
        await client.post(
            f"/v1/author/works/{work.id}/episodes", json={"title": "X"}, headers=reader
        ),
        await client.get(f"/v1/author/works/{work.id}/episodes", headers=reader),
        await client.get(f"/v1/author/episodes/{episode.id}", headers=reader),
    ]
    signed_out = [
        await client.post(f"/v1/author/works/{work.id}/episodes", json={"title": "X"}),
        await client.get(f"/v1/author/works/{work.id}/episodes"),
        await client.get(f"/v1/author/episodes/{episode.id}"),
    ]

    assert [response.status_code for response in as_reader] == [403] * 3
    assert [response.status_code for response in signed_out] == [401] * 3


async def test_fr_nv_01_an_author_renames_an_episode_and_readers_see_it_at_once(
    client: AsyncClient,
    make_user: MakeUser,
    make_work: MakeWork,
    make_episode: MakeEpisode,
    publish_text: PublishText,
    auth_headers: AuthHeaders,
) -> None:
    author = await make_user(Role.AUTHOR)
    headers = auth_headers(author)
    work = await make_work(author)
    draft = await make_episode(work, title="Working title")
    published = await make_episode(work, title="First title")
    await publish_text(published, "The text stays as it is.")

    renamed_draft = await client.patch(
        f"/v1/author/episodes/{draft.id}", json={"title": "제2화: 달빛"}, headers=headers
    )
    renamed_published = await client.patch(
        f"/v1/author/episodes/{published.id}",
        json={"title": "Chương 2: Ánh trăng"},
        headers=headers,
    )
    unchanged = await client.patch(f"/v1/author/episodes/{published.id}", json={}, headers=headers)

    assert renamed_draft.status_code == 200
    assert (renamed_draft.json()["title"], renamed_draft.json()["status"]) == (
        "제2화: 달빛",
        "draft",
    )
    assert renamed_published.json()["title"] == "Chương 2: Ánh trăng"
    assert renamed_published.json()["status"] == "published"
    assert unchanged.json()["title"] == "Chương 2: Ánh trăng"
    # The public pages show the new title; the text was not touched.
    listed = (await client.get(f"/v1/works/{work.id}/episodes")).json()
    content = (await client.get(f"/v1/episodes/{published.id}/content")).json()
    assert [episode["title"] for episode in listed] == ["Chương 2: Ánh trăng"]
    assert (content["title"], content["paragraphs"]) == (
        "Chương 2: Ánh trăng",
        ["The text stays as it is."],
    )


@pytest.mark.parametrize(
    "payload", [{"title": "  "}, {"title": "x" * 201}, {"title": "Fine", "price_coins": 0}]
)
async def test_fr_nv_01_an_invalid_rename_is_rejected(
    client: AsyncClient,
    make_user: MakeUser,
    make_work: MakeWork,
    make_episode: MakeEpisode,
    auth_headers: AuthHeaders,
    payload: dict[str, object],
) -> None:
    author = await make_user(Role.AUTHOR)
    episode = await make_episode(await make_work(author), title="Kept")

    response = await client.patch(
        f"/v1/author/episodes/{episode.id}", json=payload, headers=auth_headers(author)
    )

    assert response.status_code == 422
    fetched = await client.get(f"/v1/author/episodes/{episode.id}", headers=auth_headers(author))
    assert fetched.json()["title"] == "Kept"


async def test_fr_nv_01_a_removed_episode_cannot_be_renamed(
    client: AsyncClient,
    db_session: AsyncSession,
    make_user: MakeUser,
    make_work: MakeWork,
    make_episode: MakeEpisode,
    auth_headers: AuthHeaders,
) -> None:
    author = await make_user(Role.AUTHOR)
    episode = await make_episode(await make_work(author), title="Taken down")
    await db_session.execute(
        text("UPDATE core.episodes SET status = 'removed' WHERE id = :id"), {"id": episode.id}
    )

    response = await client.patch(
        f"/v1/author/episodes/{episode.id}", json={"title": "Back"}, headers=auth_headers(author)
    )

    assert (response.status_code, response.json()["error"]["code"]) == (409, "episode_removed")


async def test_fr_nv_01_only_the_author_of_an_episode_can_rename_it(
    client: AsyncClient,
    make_user: MakeUser,
    make_work: MakeWork,
    make_episode: MakeEpisode,
    auth_headers: AuthHeaders,
) -> None:
    author = await make_user(Role.AUTHOR)
    episode = await make_episode(await make_work(author), title="Mine")
    url = f"/v1/author/episodes/{episode.id}"
    rename = {"title": "Taken"}

    responses = [
        await client.patch(url, json=rename, headers=auth_headers(await make_user(Role.AUTHOR))),
        await client.patch(url, json=rename, headers=auth_headers(await make_user())),
        await client.patch(url, json=rename, headers=auth_headers(await make_user(Role.ADMIN))),
        await client.patch(url, json=rename),
    ]

    assert [response.status_code for response in responses] == [404, 403, 403, 401]
    fetched = await client.get(url, headers=auth_headers(author))
    assert fetched.json()["title"] == "Mine"
