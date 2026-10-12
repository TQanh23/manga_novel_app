"""FR-RD-02: a work's page, with its tags and its published episodes."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth.models import Role
from api.testing import MakePublishedWork, MakeUser, MakeWork


async def test_fr_rd_02_a_work_page_shows_the_description_the_genres_and_the_tags(
    client: AsyncClient, make_user: MakeUser, make_published_work: MakePublishedWork
) -> None:
    author = await make_user(Role.AUTHOR, display_name="김작가")
    work = await make_published_work(
        author,
        title="달빛 아래의 검",
        synopsis="회귀한 검사가 다시 길을 떠난다.",
        language="ko",
        status="completed",
        episodes=2,
        genres=["fantasy"],
        tags=["회귀", "먼치킨"],
    )

    response = await client.get(f"/v1/works/{work.id}")

    assert response.status_code == 200
    page = response.json()
    assert (page["title"], page["synopsis"]) == (
        "달빛 아래의 검",
        "회귀한 검사가 다시 길을 떠난다.",
    )
    assert (page["type"], page["language"], page["status"]) == ("novel", "ko", "completed")
    assert page["author"] == {"id": str(author.id), "display_name": "김작가"}
    assert page["genres"] == ["fantasy"]
    assert sorted(page["tags"]) == ["먼치킨", "회귀"]
    assert page["episode_count"] == 2


async def test_fr_rd_02_episodes_are_listed_in_order_with_what_they_cost(
    client: AsyncClient, make_published_work: MakePublishedWork, db_session: AsyncSession
) -> None:
    newest = datetime.now(UTC) - timedelta(hours=1)
    work = await make_published_work(episodes=3, last_published_at=newest)
    await db_session.execute(
        text(
            "UPDATE core.episodes SET price_coins = 3, wuf_eligible = true, title = '第三話'"
            " WHERE work_id = :work_id AND number = 3"
        ),
        {"work_id": work.id},
    )

    response = await client.get(f"/v1/works/{work.id}/episodes")

    assert response.status_code == 200
    episodes = response.json()
    assert [(episode["number"], episode["title"]) for episode in episodes] == [
        (1, "Episode 1"),
        (2, "Episode 2"),
        (3, "第三話"),
    ]
    assert [(episode["price_coins"], episode["wuf_eligible"]) for episode in episodes] == [
        (0, False),
        (0, False),
        (3, True),
    ]
    assert datetime.fromisoformat(episodes[2]["publish_at"]) == newest
    # The list is not the text: reading an episode is another endpoint.
    assert set(episodes[0]) == {
        "id",
        "number",
        "title",
        "publish_at",
        "price_coins",
        "wuf_eligible",
    }


async def test_fr_rd_02_a_work_with_nothing_published_answers_like_one_that_does_not_exist(
    client: AsyncClient, make_user: MakeUser, make_work: MakeWork
) -> None:
    unpublished = await make_work(await make_user(Role.AUTHOR))

    responses = [
        await client.get(f"/v1/works/{unpublished.id}"),
        await client.get(f"/v1/works/{unpublished.id}/episodes"),
        await client.get(f"/v1/works/{uuid4()}"),
        await client.get(f"/v1/works/{uuid4()}/episodes"),
    ]

    bodies = {
        response.text.replace(response.json()["error"]["request_id"], "") for response in responses
    }
    assert [response.status_code for response in responses] == [404] * 4
    assert {response.json()["error"]["code"] for response in responses} == {"work_not_found"}
    # Nothing in the answer tells the two cases apart.
    assert len(bodies) == 1


async def test_fr_rd_02_a_malformed_id_is_rejected(client: AsyncClient) -> None:
    response = await client.get("/v1/works/not-a-uuid")

    assert response.status_code == 422
