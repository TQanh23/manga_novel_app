"""FR-RD-01, FR-RD-02: an author gives a work its genres and tags."""

from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth.models import Role
from api.testing import AuthHeaders, MakeUser, MakeWork

NOVEL = {"type": "novel", "title": "The Lantern Road", "language": "en"}


async def tag_rows(session: AsyncSession, *slugs: str) -> list[tuple[str, str, str]]:
    rows = await session.execute(
        text("SELECT slug, name, kind FROM core.tags WHERE slug = ANY(:slugs) ORDER BY slug"),
        {"slugs": list(slugs)},
    )
    return [tuple(row) for row in rows]


async def test_fr_rd_01_a_work_is_created_with_genres_and_tags(
    client: AsyncClient, make_user: MakeUser, auth_headers: AuthHeaders
) -> None:
    headers = auth_headers(await make_user(Role.AUTHOR))

    created = await client.post(
        "/v1/author/works",
        json={**NOVEL, "genres": ["romance", "fantasy"], "tags": ["Slow Burn", "회귀", "転生"]},
        headers=headers,
    )
    plain = await client.post("/v1/author/works", json=NOVEL, headers=headers)
    listed = await client.get("/v1/author/works", headers=headers)

    assert created.status_code == 201
    assert created.json()["genres"] == ["fantasy", "romance"]
    assert sorted(created.json()["tags"]) == ["Slow Burn", "転生", "회귀"]
    assert (plain.json()["genres"], plain.json()["tags"]) == ([], [])
    by_id = {work["id"]: work for work in listed.json()}
    assert by_id[created.json()["id"]]["genres"] == ["fantasy", "romance"]
    assert by_id[plain.json()["id"]]["tags"] == []


async def test_fr_rd_01_an_edit_replaces_only_the_set_that_was_sent(
    client: AsyncClient, make_user: MakeUser, make_work: MakeWork, auth_headers: AuthHeaders
) -> None:
    author = await make_user(Role.AUTHOR)
    headers = auth_headers(author)
    url = f"/v1/author/works/{(await make_work(author)).id}"
    await client.patch(
        url,
        json={"genres": ["drama", "mystery"], "tags": ["Trinh thám", "Hà Nội"]},
        headers=headers,
    )

    new_genres = await client.patch(url, json={"genres": ["horror"]}, headers=headers)
    new_tags = await client.patch(url, json={"tags": ["Ma quái"]}, headers=headers)
    renamed = await client.patch(url, json={"title": "Renamed"}, headers=headers)
    cleared = await client.patch(url, json={"genres": [], "tags": []}, headers=headers)

    assert (new_genres.json()["genres"], sorted(new_genres.json()["tags"])) == (
        ["horror"],
        ["Hà Nội", "Trinh thám"],
    )
    assert (new_tags.json()["genres"], new_tags.json()["tags"]) == (["horror"], ["Ma quái"])
    # Leaving both out, or sending null, changes neither.
    assert (renamed.json()["genres"], renamed.json()["tags"]) == (["horror"], ["Ma quái"])
    assert (cleared.json()["genres"], cleared.json()["tags"]) == ([], [])
    fetched = await client.get(url, headers=headers)
    assert (fetched.json()["genres"], fetched.json()["tags"]) == ([], [])


@pytest.mark.parametrize(
    ("payload", "code"),
    [
        ({"genres": ["isekai"]}, "unknown_genre"),
        ({"genres": ["romance", "not-a-genre"]}, "unknown_genre"),
        ({"genres": ["romance", "fantasy", "drama", "comedy"]}, "validation_error"),
        ({"genres": [""]}, "validation_error"),
        ({"tags": [f"tag {n}" for n in range(11)]}, "validation_error"),
        ({"tags": ["   "]}, "validation_error"),
        ({"tags": ["x" * 31]}, "validation_error"),
        ({"tags": "not-a-list"}, "validation_error"),
        # Three genres already, and a tag that names a fourth.
        ({"genres": ["romance", "fantasy", "drama"], "tags": ["Comedy"]}, "too_many_genres"),
    ],
)
async def test_fr_rd_01_invalid_genres_and_tags_are_rejected_and_change_nothing(
    client: AsyncClient,
    make_user: MakeUser,
    make_work: MakeWork,
    auth_headers: AuthHeaders,
    payload: dict[str, Any],
    code: str,
) -> None:
    author = await make_user(Role.AUTHOR)
    headers = auth_headers(author)
    url = f"/v1/author/works/{(await make_work(author)).id}"
    await client.patch(url, json={"genres": ["action"], "tags": ["Kept"]}, headers=headers)

    edited = await client.patch(url, json=payload, headers=headers)
    created = await client.post("/v1/author/works", json={**NOVEL, **payload}, headers=headers)

    for response in (edited, created):
        assert (response.status_code, response.json()["error"]["code"]) == (422, code)
    fetched = (await client.get(url, headers=headers)).json()
    assert (fetched["genres"], fetched["tags"]) == (["action"], ["Kept"])
    assert len((await client.get("/v1/author/works", headers=headers)).json()) == 1


async def test_fr_rd_01_the_same_tag_typed_by_two_authors_is_one_tag(
    client: AsyncClient,
    make_user: MakeUser,
    make_work: MakeWork,
    auth_headers: AuthHeaders,
    db_session: AsyncSession,
) -> None:
    first, second = await make_user(Role.AUTHOR), await make_user(Role.AUTHOR)
    first_url = f"/v1/author/works/{(await make_work(first)).id}"
    second_url = f"/v1/author/works/{(await make_work(second)).id}"

    mine = await client.patch(
        first_url,
        json={"tags": ["Xuyên  Không", "xuyên không", "Học Đường"]},
        headers=auth_headers(first),
    )
    theirs = await client.patch(
        second_url, json={"tags": ["XUYÊN KHÔNG"]}, headers=auth_headers(second)
    )

    # Case and spacing do not make a new tag; the first spelling is the one shown.
    assert sorted(mine.json()["tags"]) == ["Học Đường", "Xuyên Không"]
    assert theirs.json()["tags"] == ["Xuyên Không"]
    assert await tag_rows(db_session, "xuyên-không", "học-đường") == [
        ("học-đường", "Học Đường", "tag"),
        ("xuyên-không", "Xuyên Không", "tag"),
    ]


async def test_fr_rd_01_typing_a_genres_name_as_a_tag_gives_the_work_that_genre(
    client: AsyncClient,
    make_user: MakeUser,
    make_work: MakeWork,
    auth_headers: AuthHeaders,
    db_session: AsyncSession,
) -> None:
    author = await make_user(Role.AUTHOR)
    url = f"/v1/author/works/{(await make_work(author)).id}"

    response = await client.patch(
        url, json={"tags": ["Slice of Life", "Cozy"]}, headers=auth_headers(author)
    )

    assert (response.json()["genres"], response.json()["tags"]) == (["slice-of-life"], ["Cozy"])
    assert await tag_rows(db_session, "slice-of-life") == [
        ("slice-of-life", "Slice of Life", "genre")
    ]


async def test_fr_rd_01_an_author_cannot_label_another_authors_work(
    client: AsyncClient, make_user: MakeUser, make_work: MakeWork, auth_headers: AuthHeaders
) -> None:
    author, other_author = await make_user(Role.AUTHOR), await make_user(Role.AUTHOR)
    url = f"/v1/author/works/{(await make_work(author)).id}"
    await client.patch(url, json={"genres": ["romance"]}, headers=auth_headers(author))

    response = await client.patch(
        url, json={"genres": ["horror"], "tags": ["Taken"]}, headers=auth_headers(other_author)
    )

    assert response.status_code == 404
    mine = await client.get(url, headers=auth_headers(author))
    assert (mine.json()["genres"], mine.json()["tags"]) == (["romance"], [])
