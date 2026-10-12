"""FR-NV-01: an author creates and edits their works. FR-AUTH-03: only authors may."""

from collections.abc import AsyncIterator
from typing import Any
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from api.auth.models import Role
from api.core.config import Settings
from api.testing import AuthHeaders, MakeUser, MakeWork

NOVEL = {"type": "novel", "title": "The Lantern Road", "language": "en"}


async def wuf_presets(client: AsyncClient, headers: dict[str, str]) -> list[dict[str, Any]]:
    response = await client.get("/v1/author/wuf-presets", headers=headers)
    assert response.status_code == 200
    presets: list[dict[str, Any]] = response.json()
    return presets


@pytest.fixture
async def retired_wuf_preset(migrated: None, settings: Settings) -> AsyncIterator[UUID]:
    """A wait-until-free period an admin has stopped offering.

    Only the owner role may change presets, and the API must see the change, so
    this commits and puts the preset back afterwards.
    """
    owner = create_async_engine(settings.migration_database_url)
    try:
        async with owner.begin() as connection:
            preset_id: UUID = (
                await connection.execute(
                    text(
                        "UPDATE core.config_presets SET active = false"
                        " WHERE kind = 'wuf_period' AND value = 259200 RETURNING id"
                    )
                )
            ).scalar_one()
        yield preset_id
    finally:
        async with owner.begin() as connection:
            await connection.execute(
                text("UPDATE core.config_presets SET active = true WHERE kind = 'wuf_period'")
            )
        await owner.dispose()


async def test_fr_nv_01_an_author_creates_a_work(
    client: AsyncClient, make_user: MakeUser, auth_headers: AuthHeaders, db_session: AsyncSession
) -> None:
    author = await make_user(Role.AUTHOR)

    response = await client.post(
        "/v1/author/works",
        json={**NOVEL, "synopsis": "A courier walks north."},
        headers=auth_headers(author),
    )

    assert response.status_code == 201
    work = response.json()
    assert work["type"] == "novel"
    assert work["title"] == "The Lantern Road"
    assert work["synopsis"] == "A courier walks north."
    assert work["language"] == "en"
    assert work["status"] == "ongoing"
    assert work["wuf_preset_id"] is None
    assert work["revenue_share_preset_id"] is None
    # The AI data policy starts closed: not a sample, not opted in to training.
    assert work["is_sample"] is False
    assert work["ai_opt_in_training"] is False
    stored_author = await db_session.execute(
        text("SELECT author_id FROM core.works WHERE id = :id"), {"id": work["id"]}
    )
    assert stored_author.scalar_one() == author.id


@pytest.mark.parametrize(
    ("language", "title", "synopsis"),
    [
        ("ko", "달빛 아래의 검", "회귀한 검사가 다시 길을 떠난다."),
        ("ja", "月下の剣士", "剣士は再び旅に出る。"),
        ("vi", "Kiếm sĩ dưới trăng", "Người kiếm sĩ lại lên đường."),
    ],
)
async def test_fr_nv_01_titles_and_synopses_are_kept_as_written(
    client: AsyncClient,
    make_user: MakeUser,
    auth_headers: AuthHeaders,
    language: str,
    title: str,
    synopsis: str,
) -> None:
    headers = auth_headers(await make_user(Role.AUTHOR))

    created = await client.post(
        "/v1/author/works",
        json={"type": "novel", "title": title, "synopsis": synopsis, "language": language},
        headers=headers,
    )
    fetched = await client.get(f"/v1/author/works/{created.json()['id']}", headers=headers)

    assert created.status_code == 201
    assert (fetched.json()["title"], fetched.json()["synopsis"]) == (title, synopsis)


@pytest.mark.parametrize(
    "payload",
    [
        {**NOVEL, "title": "   "},
        {**NOVEL, "title": "x" * 201},
        {**NOVEL, "type": "comic"},
        {**NOVEL, "language": "fr"},
        {"type": "novel", "language": "en"},
        # What an author may not decide for themselves.
        {**NOVEL, "is_sample": True},
        {**NOVEL, "ai_opt_in_training": True},
        {**NOVEL, "revenue_share_preset_id": str(uuid4())},
        {**NOVEL, "author_id": str(uuid4())},
    ],
)
async def test_fr_nv_01_invalid_works_are_rejected(
    client: AsyncClient, make_user: MakeUser, auth_headers: AuthHeaders, payload: dict[str, Any]
) -> None:
    headers = auth_headers(await make_user(Role.AUTHOR))

    response = await client.post("/v1/author/works", json=payload, headers=headers)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
    assert (await client.get("/v1/author/works", headers=headers)).json() == []


async def test_fr_pay_04_an_author_picks_a_wait_until_free_period_from_the_offered_ones(
    client: AsyncClient, make_user: MakeUser, auth_headers: AuthHeaders
) -> None:
    headers = auth_headers(await make_user(Role.AUTHOR))
    presets = await wuf_presets(client, headers)

    assert [preset["seconds"] for preset in presets] == [10_800, 43_200, 86_400, 259_200]

    response = await client.post(
        "/v1/author/works", json={**NOVEL, "wuf_preset_id": presets[1]["id"]}, headers=headers
    )

    assert response.status_code == 201
    assert response.json()["wuf_preset_id"] == presets[1]["id"]


async def test_fr_pay_04_a_revenue_split_or_an_unknown_id_is_not_a_wait_until_free_period(
    client: AsyncClient, make_user: MakeUser, auth_headers: AuthHeaders, db_session: AsyncSession
) -> None:
    headers = auth_headers(await make_user(Role.AUTHOR))
    revenue_split = (
        await db_session.execute(
            text("SELECT id FROM core.config_presets WHERE kind = 'revenue_share' LIMIT 1")
        )
    ).scalar_one()

    for preset_id in (revenue_split, uuid4()):
        response = await client.post(
            "/v1/author/works", json={**NOVEL, "wuf_preset_id": str(preset_id)}, headers=headers
        )

        assert response.status_code == 422
        assert response.json()["error"]["code"] == "invalid_wuf_preset"


async def test_fr_pay_04_a_retired_period_is_neither_offered_nor_accepted(
    client: AsyncClient,
    make_user: MakeUser,
    make_work: MakeWork,
    auth_headers: AuthHeaders,
    retired_wuf_preset: UUID,
) -> None:
    author = await make_user(Role.AUTHOR)
    headers = auth_headers(author)
    work = await make_work(author)

    offered = await wuf_presets(client, headers)
    created = await client.post(
        "/v1/author/works",
        json={**NOVEL, "wuf_preset_id": str(retired_wuf_preset)},
        headers=headers,
    )
    updated = await client.patch(
        f"/v1/author/works/{work.id}",
        json={"wuf_preset_id": str(retired_wuf_preset)},
        headers=headers,
    )

    assert str(retired_wuf_preset) not in [preset["id"] for preset in offered]
    assert len(offered) == 3
    assert created.json()["error"]["code"] == "invalid_wuf_preset"
    assert updated.json()["error"]["code"] == "invalid_wuf_preset"


async def test_fr_nv_01_an_author_edits_a_work_and_untouched_fields_stay(
    client: AsyncClient, make_user: MakeUser, make_work: MakeWork, auth_headers: AuthHeaders
) -> None:
    author = await make_user(Role.AUTHOR)
    headers = auth_headers(author)
    work = await make_work(author, title="Working Title", synopsis="First idea.")

    response = await client.patch(
        f"/v1/author/works/{work.id}",
        json={"title": "Đường Đèn Lồng", "status": "completed", "language": "vi"},
        headers=headers,
    )

    assert response.status_code == 200
    updated = response.json()
    assert updated["title"] == "Đường Đèn Lồng"
    assert updated["status"] == "completed"
    assert updated["language"] == "vi"
    assert updated["synopsis"] == "First idea."
    assert updated["type"] == "novel"

    unchanged = await client.patch(f"/v1/author/works/{work.id}", json={}, headers=headers)

    assert unchanged.status_code == 200
    assert unchanged.json()["title"] == "Đường Đèn Lồng"


async def test_fr_pay_04_an_author_sets_and_clears_the_wait_until_free_period(
    client: AsyncClient, make_user: MakeUser, make_work: MakeWork, auth_headers: AuthHeaders
) -> None:
    author = await make_user(Role.AUTHOR)
    headers = auth_headers(author)
    work = await make_work(author)
    preset_id = (await wuf_presets(client, headers))[0]["id"]

    chosen = await client.patch(
        f"/v1/author/works/{work.id}", json={"wuf_preset_id": preset_id}, headers=headers
    )
    renamed = await client.patch(
        f"/v1/author/works/{work.id}", json={"title": "Renamed"}, headers=headers
    )
    cleared = await client.patch(
        f"/v1/author/works/{work.id}", json={"wuf_preset_id": None}, headers=headers
    )

    assert chosen.json()["wuf_preset_id"] == preset_id
    # Leaving the field out is not the same as sending null.
    assert renamed.json()["wuf_preset_id"] == preset_id
    assert cleared.json()["wuf_preset_id"] is None


@pytest.mark.parametrize(
    "payload",
    [{"type": "manga"}, {"is_sample": True}, {"ai_opt_in_training": True}, {"title": ""}],
)
async def test_fr_nv_01_an_edit_cannot_change_the_type_or_the_ai_policy_flags(
    client: AsyncClient,
    make_user: MakeUser,
    make_work: MakeWork,
    auth_headers: AuthHeaders,
    payload: dict[str, Any],
) -> None:
    author = await make_user(Role.AUTHOR)
    work = await make_work(author)

    response = await client.patch(
        f"/v1/author/works/{work.id}", json=payload, headers=auth_headers(author)
    )

    assert response.status_code == 422
    fetched = await client.get(f"/v1/author/works/{work.id}", headers=auth_headers(author))
    assert fetched.json()["type"] == "novel"
    assert fetched.json()["is_sample"] is False
    assert fetched.json()["ai_opt_in_training"] is False


async def test_fr_nv_01_an_author_lists_only_their_own_works_newest_first(
    client: AsyncClient, make_user: MakeUser, make_work: MakeWork, auth_headers: AuthHeaders
) -> None:
    author, other_author = await make_user(Role.AUTHOR), await make_user(Role.AUTHOR)
    first = await make_work(author, title="First")
    await make_work(other_author, title="Not Mine")
    second = await make_work(author, title="Second")

    response = await client.get("/v1/author/works", headers=auth_headers(author))

    assert response.status_code == 200
    assert [work["id"] for work in response.json()] == [str(second.id), str(first.id)]


async def test_fr_nv_01_another_authors_work_does_not_exist_as_far_as_an_author_can_tell(
    client: AsyncClient, make_user: MakeUser, make_work: MakeWork, auth_headers: AuthHeaders
) -> None:
    author, other_author = await make_user(Role.AUTHOR), await make_user(Role.AUTHOR)
    work = await make_work(author, title="Mine")
    headers = auth_headers(other_author)

    fetched = await client.get(f"/v1/author/works/{work.id}", headers=headers)
    updated = await client.patch(
        f"/v1/author/works/{work.id}", json={"title": "Taken"}, headers=headers
    )
    missing = await client.get(f"/v1/author/works/{uuid4()}", headers=headers)

    for response in (fetched, updated, missing):
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "work_not_found"
    mine = await client.get(f"/v1/author/works/{work.id}", headers=auth_headers(author))
    assert mine.json()["title"] == "Mine"


@pytest.mark.parametrize("role", [Role.READER, Role.ADMIN])
async def test_fr_auth_03_readers_and_admins_are_not_authors(
    client: AsyncClient,
    make_user: MakeUser,
    make_work: MakeWork,
    auth_headers: AuthHeaders,
    role: Role,
) -> None:
    work = await make_work(await make_user(Role.AUTHOR))
    headers = auth_headers(await make_user(role))

    responses = [
        await client.post("/v1/author/works", json=NOVEL, headers=headers),
        await client.get("/v1/author/works", headers=headers),
        await client.get(f"/v1/author/works/{work.id}", headers=headers),
        await client.patch(f"/v1/author/works/{work.id}", json={"title": "X"}, headers=headers),
        await client.get("/v1/author/wuf-presets", headers=headers),
    ]

    assert [response.status_code for response in responses] == [403] * 5


async def test_fr_auth_03_author_routes_require_sign_in(client: AsyncClient) -> None:
    responses = [
        await client.post("/v1/author/works", json=NOVEL),
        await client.get("/v1/author/works"),
        await client.get(f"/v1/author/works/{uuid4()}"),
        await client.get("/v1/author/wuf-presets"),
    ]

    assert [response.status_code for response in responses] == [401] * 4
