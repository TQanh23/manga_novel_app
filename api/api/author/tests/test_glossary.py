"""FR-NV-03: an author keeps a glossary of a work's characters, places and terms."""

from collections.abc import Callable
from typing import Any
from uuid import uuid4

import pytest
from httpx import AsyncClient

from api.auth.models import Role, User
from api.catalogue.models import Work
from api.testing import AuthHeaders, MakeUser, MakeWork

LogLines = Callable[[], list[dict[str, Any]]]

HANEUL = {
    "kind": "character",
    "name": "김하늘",
    "aliases": ["하늘", "ハヌル", "Hạ Nựu"],
    "attributes": {"눈 색": "갈색", "tuổi": 17, "関係": {"姉": "김바다"}, "thuận tay trái": True},
    "translations": {"ja": "キム・ハヌル", "vi": "Kim Hạ Nựu", "en": "Kim Ha-neul"},
}


@pytest.fixture
async def author(make_user: MakeUser) -> User:
    return await make_user(Role.AUTHOR)


@pytest.fixture
async def work(author: User, make_work: MakeWork) -> Work:
    return await make_work(author, language="ko")


async def add(
    client: AsyncClient, headers: dict[str, str], work: Work, entry: dict[str, Any]
) -> dict[str, Any]:
    response = await client.post(
        f"/v1/author/works/{work.id}/glossary", json=entry, headers=headers
    )
    assert response.status_code == 201, response.text
    created: dict[str, Any] = response.json()
    return created


async def test_fr_nv_03_an_entry_keeps_korean_japanese_and_vietnamese_exactly_as_written(
    client: AsyncClient, auth_headers: AuthHeaders, author: User, work: Work
) -> None:
    headers = auth_headers(author)

    created = await add(client, headers, work, HANEUL)
    listed = await client.get(f"/v1/author/works/{work.id}/glossary", headers=headers)

    assert created["work_id"] == str(work.id)
    assert {key: created[key] for key in HANEUL} == HANEUL
    assert listed.status_code == 200
    assert listed.json() == [created]


async def test_fr_nv_03_an_entry_needs_only_a_kind_and_a_name(
    client: AsyncClient, auth_headers: AuthHeaders, author: User, work: Work
) -> None:
    created = await add(client, auth_headers(author), work, {"kind": "place", "name": "  서울  "})

    assert (created["kind"], created["name"]) == ("place", "서울")
    assert (created["aliases"], created["attributes"], created["translations"]) == ([], {}, {})


async def test_fr_nv_03_the_glossary_is_listed_by_kind_then_name(
    client: AsyncClient, auth_headers: AuthHeaders, author: User, work: Work
) -> None:
    headers = auth_headers(author)
    for kind, name in [
        ("term", "검기"),
        ("place", "한강"),
        ("character", "하늘"),
        ("character", "바다"),
    ]:
        await add(client, headers, work, {"kind": kind, "name": name})

    listed = await client.get(f"/v1/author/works/{work.id}/glossary", headers=headers)

    assert [(entry["kind"], entry["name"]) for entry in listed.json()] == [
        ("character", "바다"),
        ("character", "하늘"),
        ("place", "한강"),
        ("term", "검기"),
    ]


async def test_fr_nv_03_an_edit_replaces_what_was_sent_and_keeps_the_rest(
    client: AsyncClient, auth_headers: AuthHeaders, author: User, work: Work
) -> None:
    headers = auth_headers(author)
    entry = await add(client, headers, work, HANEUL)
    url = f"/v1/author/works/{work.id}/glossary/{entry['id']}"

    renamed = await client.patch(url, json={"name": "김하늘 (金하늘)"}, headers=headers)
    replaced = await client.patch(
        url,
        json={"aliases": ["하늘이"], "attributes": {"tuổi": 18}, "translations": {"en": "Haneul"}},
        headers=headers,
    )
    cleared = await client.patch(url, json={"aliases": [], "attributes": {}}, headers=headers)
    untouched = await client.patch(url, json={}, headers=headers)

    assert renamed.status_code == 200
    assert renamed.json()["name"] == "김하늘 (金하늘)"
    assert renamed.json()["aliases"] == HANEUL["aliases"]
    assert renamed.json()["attributes"] == HANEUL["attributes"]
    # A list or an object that is sent replaces the old one whole.
    assert replaced.json()["aliases"] == ["하늘이"]
    assert replaced.json()["attributes"] == {"tuổi": 18}
    assert replaced.json()["translations"] == {"en": "Haneul"}
    assert (cleared.json()["aliases"], cleared.json()["attributes"]) == ([], {})
    assert cleared.json()["translations"] == {"en": "Haneul"}
    assert untouched.json()["name"] == "김하늘 (金하늘)"


async def test_fr_nv_03_a_work_lists_a_name_once_per_kind(
    client: AsyncClient,
    auth_headers: AuthHeaders,
    make_work: MakeWork,
    author: User,
    work: Work,
) -> None:
    headers = auth_headers(author)
    url = f"/v1/author/works/{work.id}/glossary"
    city = await add(client, headers, work, {"kind": "place", "name": "Hà Nội"})
    # The same name is fine as another kind, and in another work.
    person = await add(client, headers, work, {"kind": "character", "name": "Hà Nội"})
    await add(client, headers, await make_work(author), {"kind": "place", "name": "Hà Nội"})

    again = await client.post(url, json={"kind": "place", "name": "Hà Nội"}, headers=headers)
    renamed_onto = await client.patch(
        f"{url}/{person['id']}", json={"kind": "place"}, headers=headers
    )
    same_name_kept = await client.patch(
        f"{url}/{city['id']}", json={"name": "Hà Nội", "aliases": ["Thăng Long"]}, headers=headers
    )

    for response in (again, renamed_onto):
        assert (response.status_code, response.json()["error"]["code"]) == (
            409,
            "glossary_entry_exists",
        )
    assert same_name_kept.status_code == 200
    listed = await client.get(url, headers=headers)
    assert [(entry["kind"], entry["name"]) for entry in listed.json()] == [
        ("character", "Hà Nội"),
        ("place", "Hà Nội"),
    ]


async def test_fr_nv_03_an_author_deletes_an_entry_and_only_that_one(
    client: AsyncClient, auth_headers: AuthHeaders, author: User, work: Work
) -> None:
    headers = auth_headers(author)
    haneul = await add(client, headers, work, HANEUL)
    seoul = await add(client, headers, work, {"kind": "place", "name": "서울"})
    url = f"/v1/author/works/{work.id}/glossary"

    deleted = await client.delete(f"{url}/{haneul['id']}", headers=headers)
    again = await client.delete(f"{url}/{haneul['id']}", headers=headers)

    assert (deleted.status_code, deleted.content) == (204, b"")
    assert (again.status_code, again.json()["error"]["code"]) == (404, "glossary_entry_not_found")
    assert (await client.get(url, headers=headers)).json() == [seoul]


async def test_fr_nv_03_a_deleted_name_can_be_noted_again(
    client: AsyncClient, auth_headers: AuthHeaders, author: User, work: Work
) -> None:
    headers = auth_headers(author)
    entry = await add(client, headers, work, HANEUL)

    await client.delete(f"/v1/author/works/{work.id}/glossary/{entry['id']}", headers=headers)
    again = await add(client, headers, work, {"kind": "character", "name": HANEUL["name"]})

    assert again["id"] != entry["id"]


@pytest.mark.parametrize(
    "payload",
    [
        {"kind": "item", "name": "Sword"},
        {"kind": "character"},
        {"name": "No kind"},
        {"kind": "character", "name": "   "},
        {"kind": "character", "name": "가" * 101},
        {"kind": "character", "name": "A", "aliases": [f"alias {n}" for n in range(21)]},
        {"kind": "character", "name": "A", "aliases": [""]},
        {"kind": "character", "name": "A", "aliases": "not-a-list"},
        {"kind": "character", "name": "A", "attributes": {f"key {n}": n for n in range(31)}},
        {"kind": "character", "name": "A", "attributes": {"note": "가" * 4_000}},
        {"kind": "character", "name": "A", "attributes": {"": "empty key"}},
        {"kind": "character", "name": "A", "attributes": ["not", "an", "object"]},
        # Only the content languages have a translation slot.
        {"kind": "character", "name": "A", "translations": {"fr": "Ciel"}},
        {"kind": "character", "name": "A", "translations": {"ja": ""}},
        {"kind": "character", "name": "A", "work_id": str(uuid4())},
    ],
)
async def test_fr_nv_03_invalid_entries_are_rejected(
    client: AsyncClient,
    auth_headers: AuthHeaders,
    author: User,
    work: Work,
    payload: dict[str, Any],
) -> None:
    headers = auth_headers(author)
    url = f"/v1/author/works/{work.id}/glossary"

    response = await client.post(url, json=payload, headers=headers)

    assert (response.status_code, response.json()["error"]["code"]) == (422, "validation_error")
    assert (await client.get(url, headers=headers)).json() == []


async def test_fr_nv_03_an_invalid_edit_changes_nothing(
    client: AsyncClient, auth_headers: AuthHeaders, author: User, work: Work
) -> None:
    headers = auth_headers(author)
    entry = await add(client, headers, work, HANEUL)
    url = f"/v1/author/works/{work.id}/glossary/{entry['id']}"

    responses = [
        await client.patch(url, json={"kind": "item"}, headers=headers),
        await client.patch(url, json={"name": ""}, headers=headers),
        await client.patch(url, json={"translations": {"xx": "?"}}, headers=headers),
        await client.patch(url, json={"id": str(uuid4())}, headers=headers),
    ]

    assert [response.status_code for response in responses] == [422] * 4
    listed = await client.get(f"/v1/author/works/{work.id}/glossary", headers=headers)
    assert listed.json() == [entry]


async def test_fr_nv_03_another_authors_glossary_does_not_exist_as_far_as_an_author_can_tell(
    client: AsyncClient,
    make_user: MakeUser,
    make_work: MakeWork,
    auth_headers: AuthHeaders,
    author: User,
    work: Work,
) -> None:
    entry = await add(client, auth_headers(author), work, HANEUL)
    intruder = await make_user(Role.AUTHOR)
    headers = auth_headers(intruder)
    own_work = await make_work(intruder)
    url = f"/v1/author/works/{work.id}/glossary"

    on_their_work = [
        await client.get(url, headers=headers),
        await client.post(url, json={"kind": "term", "name": "Uninvited"}, headers=headers),
        await client.patch(f"{url}/{entry['id']}", json={"name": "Taken"}, headers=headers),
        await client.delete(f"{url}/{entry['id']}", headers=headers),
    ]
    # An entry is reached only through its own work.
    through_own_work = await client.patch(
        f"/v1/author/works/{own_work.id}/glossary/{entry['id']}",
        json={"name": "Taken"},
        headers=headers,
    )
    deleted_through_own_work = await client.delete(
        f"/v1/author/works/{own_work.id}/glossary/{entry['id']}", headers=headers
    )
    unknown = await client.patch(
        f"/v1/author/works/{own_work.id}/glossary/{uuid4()}", json={"name": "X"}, headers=headers
    )

    assert [(r.status_code, r.json()["error"]["code"]) for r in on_their_work] == [
        (404, "work_not_found")
    ] * 4
    for response in (through_own_work, deleted_through_own_work, unknown):
        assert (response.status_code, response.json()["error"]["code"]) == (
            404,
            "glossary_entry_not_found",
        )
    for response in (*on_their_work, through_own_work):
        assert "김하늘" not in response.text
    mine = await client.get(url, headers=auth_headers(author))
    assert mine.json() == [entry]


async def test_fr_auth_03_glossary_routes_are_for_authors_only(
    client: AsyncClient,
    make_user: MakeUser,
    auth_headers: AuthHeaders,
    author: User,
    work: Work,
) -> None:
    entry = await add(client, auth_headers(author), work, HANEUL)
    url = f"/v1/author/works/{work.id}/glossary"

    for headers, expected in (
        (auth_headers(await make_user()), 403),
        (auth_headers(await make_user(Role.ADMIN)), 403),
        (None, 401),
    ):
        responses = [
            await client.get(url, headers=headers),
            await client.post(url, json={"kind": "term", "name": "X"}, headers=headers),
            await client.patch(f"{url}/{entry['id']}", json={"name": "X"}, headers=headers),
            await client.delete(f"{url}/{entry['id']}", headers=headers),
        ]

        assert [response.status_code for response in responses] == [expected] * 4


async def test_the_glossary_never_reaches_the_logs(
    client: AsyncClient,
    auth_headers: AuthHeaders,
    log_lines: LogLines,
    author: User,
    work: Work,
) -> None:
    headers = auth_headers(author)

    entry = await add(client, headers, work, HANEUL)
    await client.patch(
        f"/v1/author/works/{work.id}/glossary/{entry['id']}",
        json={"attributes": {"비밀": "아무도 모르는 사실"}},
        headers=headers,
    )
    await client.delete(f"/v1/author/works/{work.id}/glossary/{entry['id']}", headers=headers)

    lines = log_lines()
    assert {"glossary_entry_created", "glossary_entry_updated", "glossary_entry_deleted"} <= {
        line.get("event") for line in lines
    }
    logged = str(lines)
    for secret in ("김하늘", "갈색", "Kim Ha-neul", "아무도 모르는"):
        assert secret not in logged
