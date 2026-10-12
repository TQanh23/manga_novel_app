"""NFR-06, end to end: what one author saves, no other author can reach.

These requests really commit, each on a connection from the pool, so an author
context left behind by one request would show up in the next.
"""

from typing import Any

from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from api.testing import TEST_PASSWORD

NOVEL = {"type": "novel", "title": "Private", "language": "vi"}


async def sign_up_author(client: AsyncClient, email: str) -> dict[str, str]:
    credentials = {"email": email, "password": TEST_PASSWORD}
    await client.post("/v1/auth/register", json={**credentials, "display_name": email})
    tokens = (await client.post("/v1/auth/login", json=credentials)).json()
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    became_author = await client.post("/v1/me/roles/author", headers=headers)
    assert became_author.status_code == 200, became_author.text
    return headers


async def start_episode(client: AsyncClient, headers: dict[str, str]) -> dict[str, Any]:
    work = (await client.post("/v1/author/works", json=NOVEL, headers=headers)).json()
    response = await client.post(
        f"/v1/author/works/{work['id']}/episodes", json={"title": "Chương 1"}, headers=headers
    )
    assert response.status_code == 201, response.text
    episode: dict[str, Any] = response.json()
    return episode


async def versions_visible_without_an_author(
    sessions: async_sessionmaker[AsyncSession],
) -> int:
    async with sessions() as session:
        rows = await session.execute(text("SELECT count(*) FROM core.episode_versions"))
        return int(rows.scalar_one())


async def test_nfr_06_one_authors_drafts_are_out_of_every_other_authors_reach(
    committing_client: AsyncClient, committed_sessions: async_sessionmaker[AsyncSession]
) -> None:
    client = committing_client
    alice = await sign_up_author(client, "alice@example.com")
    bob = await sign_up_author(client, "bob@example.com")
    episode = await start_episode(client, alice)
    base = f"/v1/author/episodes/{episode['id']}"
    saved = [
        (await client.put(f"{base}/draft", json={"body_md": body}, headers=alice)).json()["id"]
        for body in ("초안 하나", "下書き二", "Bản nháp ba")
    ]

    as_bob = [
        await client.get(f"/v1/author/works/{episode['work_id']}", headers=bob),
        await client.get(f"/v1/author/works/{episode['work_id']}/episodes", headers=bob),
        await client.get(base, headers=bob),
        await client.get(f"{base}/draft", headers=bob),
        await client.put(f"{base}/draft", json={"body_md": "Bob was here"}, headers=bob),
        await client.get(f"{base}/versions", headers=bob),
        await client.get(f"{base}/versions/{saved[0]}", headers=bob),
        await client.post(f"{base}/versions/{saved[0]}/restore", headers=bob),
        await client.post(f"{base}/publish", headers=bob),
    ]

    assert [response.status_code for response in as_bob] == [404] * 9
    assert (await client.get("/v1/author/works", headers=bob)).json() == []

    # Bob's own history holds his save and nothing of Alice's, straight after
    # her requests ran on the same pool.
    bobs_episode = await start_episode(client, bob)
    bobs_base = f"/v1/author/episodes/{bobs_episode['id']}"
    bobs_save = await client.put(f"{bobs_base}/draft", json={"body_md": "Của Bob"}, headers=bob)
    bobs_history = (await client.get(f"{bobs_base}/versions", headers=bob)).json()
    alices_history = (await client.get(f"{base}/versions", headers=alice)).json()

    assert [version["id"] for version in bobs_history] == [bobs_save.json()["id"]]
    assert [version["id"] for version in alices_history] == saved[::-1]

    # Outside the API, a transaction that names no author sees no draft at all
    # until one is published, and then only that one.
    assert await versions_visible_without_an_author(committed_sessions) == 0

    published = await client.post(f"{base}/publish", headers=alice)

    assert published.status_code == 200
    assert published.json()["published_version_id"] == saved[2]
    assert await versions_visible_without_an_author(committed_sessions) == 1
