"""NFR-05: auth routes are rate limited by address and by account, in Redis."""

import pytest
from httpx import AsyncClient
from redis.exceptions import RedisError

from api.core import rate_limit
from api.core.config import Settings
from api.testing import TEST_PASSWORD, AuthHeaders, MakeUser


async def wrong_login(client: AsyncClient, email: str) -> int:
    response = await client.post(
        "/v1/auth/login", json={"email": email, "password": "not the password"}
    )
    return response.status_code


async def test_nfr_05_login_is_limited_per_account(
    client: AsyncClient, make_user: MakeUser, settings: Settings
) -> None:
    await make_user(email="target@example.com")
    limit = settings.rate_limit_auth_per_identity

    allowed = [await wrong_login(client, "target@example.com") for _ in range(limit)]
    blocked = await client.post(
        "/v1/auth/login", json={"email": "Target@Example.com", "password": TEST_PASSWORD}
    )

    assert allowed == [401] * limit
    # Even the right password waits once the account's limit is spent.
    assert blocked.status_code == 429
    assert blocked.json()["error"]["code"] == "rate_limited"
    assert 1 <= int(blocked.headers["Retry-After"]) <= settings.rate_limit_window_seconds


async def test_nfr_05_one_accounts_limit_does_not_block_another(
    client: AsyncClient, make_user: MakeUser, settings: Settings
) -> None:
    await make_user(email="other@example.com")
    for _ in range(settings.rate_limit_auth_per_identity + 1):
        await wrong_login(client, "target@example.com")

    response = await client.post(
        "/v1/auth/login", json={"email": "other@example.com", "password": TEST_PASSWORD}
    )

    assert response.status_code == 200


async def test_nfr_05_register_is_limited_per_address(
    client: AsyncClient, settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "rate_limit_auth_per_ip", 2)

    statuses = [
        (
            await client.post(
                "/v1/auth/register",
                json={
                    "email": f"new{number}@example.com",
                    "password": TEST_PASSWORD,
                    "display_name": "New",
                },
            )
        ).status_code
        for number in range(3)
    ]

    assert statuses == [201, 201, 429]


async def test_nfr_05_signed_in_routes_are_limited_per_user(
    client: AsyncClient,
    make_user: MakeUser,
    auth_headers: AuthHeaders,
    settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "rate_limit_auth_per_identity", 1)
    first_user, second_user = await make_user(), await make_user()

    first = await client.post("/v1/me/roles/author", headers=auth_headers(first_user))
    again = await client.post("/v1/me/roles/author", headers=auth_headers(first_user))
    other = await client.post("/v1/me/roles/author", headers=auth_headers(second_user))

    assert (first.status_code, again.status_code, other.status_code) == (200, 429, 200)


async def test_nfr_05_rate_limiting_fails_open_when_redis_is_down(
    client: AsyncClient, make_user: MakeUser, monkeypatch: pytest.MonkeyPatch
) -> None:
    class DownRedis:
        def pipeline(self, transaction: bool = True) -> None:
            raise RedisError("connection refused")

    user = await make_user()
    monkeypatch.setattr(rate_limit, "get_redis", DownRedis)

    response = await client.post(
        "/v1/auth/login", json={"email": user.email, "password": TEST_PASSWORD}
    )

    assert response.status_code == 200
