"""FR-RD-06: search by title, author or tag, with or without diacritics (D9)."""

import unicodedata
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth.models import Role
from api.testing import MakePublishedWork, MakeUser


def ago(**delta: float) -> datetime:
    return datetime.now(UTC) - timedelta(**delta)


async def found(client: AsyncClient, q: str) -> list[str]:
    response = await client.get("/v1/search", params={"q": q})
    assert response.status_code == 200, response.text
    return [work["title"] for work in response.json()["items"]]


@pytest.mark.parametrize(
    "query",
    [
        "kiem si",
        "Kiếm sĩ",
        "KIEM SI DUOI TRANG",
        "kiếm sĩ dưới trăng",
        "duoi trang",
        "dưới",
        # Typed with combining marks instead of precomposed letters.
        unicodedata.normalize("NFD", "Kiếm sĩ"),
    ],
)
async def test_d9_a_vietnamese_title_is_found_with_or_without_its_diacritics(
    client: AsyncClient, make_published_work: MakePublishedWork, query: str
) -> None:
    await make_published_work(title="Kiếm sĩ dưới trăng", language="vi")
    await make_published_work(title="The Lantern Road")

    assert await found(client, query) == ["Kiếm sĩ dưới trăng"]


async def test_d9_a_title_stored_with_combining_marks_is_found_too(
    client: AsyncClient, make_published_work: MakePublishedWork
) -> None:
    stored = unicodedata.normalize("NFD", "Đường Đèn Lồng")
    await make_published_work(title=stored, language="vi")

    assert await found(client, "duong den long") == [stored]
    assert await found(client, "Đường Đèn") == [stored]


@pytest.mark.parametrize(
    ("title", "query"),
    [
        ("달빛 아래의 검", "아래"),
        ("달빛 아래의 검", "검"),
        ("月下の剣士", "剣士"),
        ("月下の剣士", "の"),
        ("The Lantern Road", "LANTERN"),
        ("The Lantern Road", "tern ro"),
    ],
)
async def test_fr_rd_06_any_part_of_a_title_matches_in_every_content_language(
    client: AsyncClient, make_published_work: MakePublishedWork, title: str, query: str
) -> None:
    await make_published_work(title=title)
    await make_published_work(title="Nothing in common")

    assert await found(client, query) == [title]


async def test_fr_rd_06_a_work_is_found_by_its_authors_name_and_by_its_tags(
    client: AsyncClient, make_user: MakeUser, make_published_work: MakePublishedWork
) -> None:
    author = await make_user(Role.AUTHOR, display_name="Nguyễn Nhật Ánh")
    await make_published_work(author, title="By the author")
    await make_published_work(title="With the tag", tags=["Xuyên không"])
    await make_published_work(title="With the genre", genres=["romance"])
    await make_published_work(title="Unrelated")

    assert await found(client, "nhat anh") == ["By the author"]
    assert await found(client, "xuyen khong") == ["With the tag"]
    assert await found(client, "Romance") == ["With the genre"]


async def test_d9_a_title_matching_with_its_diacritics_comes_before_one_matching_without(
    client: AsyncClient, make_published_work: MakePublishedWork
) -> None:
    await make_published_work(title="Kiếm sĩ dưới trăng", last_published_at=ago(days=5))
    await make_published_work(title="Kiêm nhiệm", last_published_at=ago(hours=1))

    # Typed with diacritics: the exact word first, the look-alike after it.
    assert await found(client, "kiếm") == ["Kiếm sĩ dưới trăng", "Kiêm nhiệm"]
    # Typed without: both match equally, so the newer one leads.
    assert await found(client, "kiem") == ["Kiêm nhiệm", "Kiếm sĩ dưới trăng"]


async def test_fr_rd_06_a_title_match_comes_before_a_tag_or_author_match(
    client: AsyncClient, make_user: MakeUser, make_published_work: MakePublishedWork
) -> None:
    author = await make_user(Role.AUTHOR, display_name="Moon Writer")
    await make_published_work(title="Under the Moon", last_published_at=ago(days=9))
    await make_published_work(title="Tagged", tags=["Moonlight"], last_published_at=ago(days=1))
    await make_published_work(author, title="By name", last_published_at=ago(hours=1))

    assert await found(client, "moon") == ["Under the Moon", "By name", "Tagged"]


async def test_fr_rd_06_percent_and_underscore_are_matched_as_typed(
    client: AsyncClient, make_published_work: MakePublishedWork
) -> None:
    await make_published_work(title="100% Love")
    await make_published_work(title="snake_case")
    await make_published_work(title="Plain")

    assert await found(client, "%") == ["100% Love"]
    assert await found(client, "_") == ["snake_case"]
    assert await found(client, "0% L") == ["100% Love"]
    assert await found(client, "\\") == []


async def test_fr_rd_06_search_results_are_paged(
    client: AsyncClient, make_published_work: MakePublishedWork
) -> None:
    for number in range(1, 4):
        await make_published_work(title=f"Saga {number}", last_published_at=ago(hours=number))

    first = (await client.get("/v1/search", params={"q": "saga", "limit": 2})).json()
    rest = (await client.get("/v1/search", params={"q": "saga", "limit": 2, "offset": 2})).json()

    assert ([work["title"] for work in first["items"]], first["has_more"]) == (
        ["Saga 1", "Saga 2"],
        True,
    )
    assert ([work["title"] for work in rest["items"]], rest["has_more"]) == (["Saga 3"], False)


@pytest.mark.parametrize("params", [{}, {"q": ""}, {"q": "   "}, {"q": "x" * 101}])
async def test_fr_rd_06_a_search_needs_something_to_look_for(
    client: AsyncClient, params: dict[str, str]
) -> None:
    response = await client.get("/v1/search", params=params)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


async def test_d9_search_normalize_drops_diacritics_and_case_but_leaves_other_scripts(
    db_session: AsyncSession,
) -> None:
    rows = await db_session.execute(
        text("SELECT core.search_normalize(value) FROM unnest(CAST(:values AS text[])) AS value"),
        {
            "values": [
                "Đường Đèn Lồng",
                unicodedata.normalize("NFD", "Kiếm sĩ dưới trăng"),
                "달빛 아래의 검",
                "月下の剣士",
            ]
        },
    )

    assert list(rows.scalars()) == [
        "duong den long",
        "kiem si duoi trang",
        "달빛 아래의 검",
        "月下の剣士",
    ]


async def test_d9_titles_author_names_and_tags_have_a_trigram_index_on_the_normalized_text(
    db_session: AsyncSession,
) -> None:
    rows = await db_session.execute(
        text(
            "SELECT tablename, indexdef FROM pg_indexes"
            " WHERE schemaname = 'core' AND indexname LIKE '%\\_trgm' ORDER BY tablename"
        )
    )
    indexes = {row.tablename: row.indexdef for row in rows}

    assert sorted(indexes) == ["tags", "users", "works"]
    for definition in indexes.values():
        assert "USING gin" in definition
        assert "search_normalize" in definition
        assert "gin_trgm_ops" in definition
