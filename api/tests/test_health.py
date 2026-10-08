import pytest
from httpx import AsyncClient

from api.core import health


async def test_healthz_returns_ok(client: AsyncClient) -> None:
    response = await client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.usefixtures("engine")
async def test_readyz_is_ok_when_postgres_and_redis_answer(client: AsyncClient) -> None:
    response = await client.get("/readyz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "checks": {"postgres": "ok", "redis": "ok"}}


@pytest.mark.usefixtures("engine")
async def test_readyz_is_503_when_a_dependency_is_down(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def unreachable() -> None:
        raise ConnectionError("redis is down")

    monkeypatch.setattr(health, "ping_redis", unreachable)

    response = await client.get("/readyz")

    assert response.status_code == 503
    assert response.json() == {
        "status": "unavailable",
        "checks": {"postgres": "ok", "redis": "down"},
    }


@pytest.mark.usefixtures("engine")
async def test_readyz_gives_up_on_a_dependency_that_hangs(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    import asyncio

    async def hangs() -> None:
        await asyncio.sleep(60)

    monkeypatch.setattr(health, "ping_postgres", hangs)
    monkeypatch.setattr(health, "_CHECK_TIMEOUT_SECONDS", 0.05)

    response = await client.get("/readyz")

    assert response.status_code == 503
    assert response.json()["checks"] == {"postgres": "down", "redis": "ok"}
