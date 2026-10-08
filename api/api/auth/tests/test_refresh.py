"""NFR-05: refresh tokens rotate, work once, and a replayed one ends the session."""

import asyncio
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient, Response
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth.models import RefreshToken, User
from api.core.config import Settings
from api.testing import TEST_PASSWORD, MakeUser


async def login(client: AsyncClient, user: User, *, transport: str = "body") -> Response:
    response = await client.post(
        "/v1/auth/login",
        json={"email": user.email, "password": TEST_PASSWORD, "token_transport": transport},
    )
    assert response.status_code == 200
    return response


async def refresh(client: AsyncClient, refresh_token: str) -> Response:
    return await client.post("/v1/auth/refresh", json={"refresh_token": refresh_token})


@pytest.fixture
def no_grace(settings: Settings, monkeypatch: pytest.MonkeyPatch) -> None:
    """Treat any second use of a refresh token as a replay, however soon."""
    monkeypatch.setattr(settings, "refresh_reuse_grace_seconds", -1)


async def test_nfr_05_refresh_returns_a_new_pair(client: AsyncClient, make_user: MakeUser) -> None:
    user = await make_user()
    first = (await login(client, user)).json()

    response = await refresh(client, first["refresh_token"])

    assert response.status_code == 200
    second = response.json()
    assert second["refresh_token"] != first["refresh_token"]
    assert second["access_token"] != first["access_token"]
    assert second["user"]["id"] == str(user.id)

    me = await client.get("/v1/me", headers={"Authorization": f"Bearer {second['access_token']}"})
    assert me.status_code == 200


@pytest.mark.usefixtures("no_grace")
async def test_nfr_05_a_replayed_refresh_token_revokes_the_whole_session(
    client: AsyncClient, make_user: MakeUser
) -> None:
    user = await make_user()
    first = (await login(client, user)).json()
    second = (await refresh(client, first["refresh_token"])).json()

    replay = await refresh(client, first["refresh_token"])
    after_replay = await refresh(client, second["refresh_token"])

    assert replay.status_code == 401
    assert replay.json()["error"]["code"] == "invalid_refresh_token"
    # The newest token dies too: whoever holds it may be the one who stole it.
    assert after_replay.status_code == 401


@pytest.mark.usefixtures("no_grace")
async def test_nfr_05_a_replay_does_not_touch_the_users_other_sessions(
    client: AsyncClient, make_user: MakeUser
) -> None:
    user = await make_user()
    phone = (await login(client, user)).json()
    laptop = (await login(client, user)).json()
    await refresh(client, phone["refresh_token"])

    await refresh(client, phone["refresh_token"])

    assert (await refresh(client, laptop["refresh_token"])).status_code == 200


async def test_nfr_05_a_duplicate_refresh_within_the_grace_window_keeps_the_session(
    client: AsyncClient, make_user: MakeUser
) -> None:
    user = await make_user()
    first = (await login(client, user)).json()
    second = (await refresh(client, first["refresh_token"])).json()

    duplicate = await refresh(client, first["refresh_token"])

    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "refresh_conflict"
    assert (await refresh(client, second["refresh_token"])).status_code == 200


async def test_nfr_05_two_concurrent_refreshes_with_one_token_issue_one_pair(
    committing_client: AsyncClient,
) -> None:
    client = committing_client
    await client.post(
        "/v1/auth/register",
        json={"email": "racer@example.com", "password": TEST_PASSWORD, "display_name": "Racer"},
    )
    tokens = (
        await client.post(
            "/v1/auth/login", json={"email": "racer@example.com", "password": TEST_PASSWORD}
        )
    ).json()

    responses = await asyncio.gather(
        refresh(client, tokens["refresh_token"]), refresh(client, tokens["refresh_token"])
    )

    assert sorted(response.status_code for response in responses) == [200, 409]


async def test_nfr_05_an_expired_refresh_token_is_rejected(
    client: AsyncClient, make_user: MakeUser, db_session: AsyncSession
) -> None:
    user = await make_user()
    tokens = (await login(client, user)).json()
    await db_session.execute(
        update(RefreshToken).values(expires_at=datetime.now(UTC) - timedelta(seconds=1))
    )

    response = await refresh(client, tokens["refresh_token"])

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_refresh_token"


@pytest.mark.parametrize("payload", [{"refresh_token": "never-issued"}, {}, None])
async def test_nfr_05_an_unknown_or_missing_refresh_token_is_rejected(
    client: AsyncClient, payload: dict[str, str] | None
) -> None:
    response = await client.post("/v1/auth/refresh", json=payload)

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_refresh_token"


async def test_nfr_05_logout_ends_the_session(client: AsyncClient, make_user: MakeUser) -> None:
    user = await make_user()
    tokens = (await login(client, user)).json()

    response = await client.post("/v1/auth/logout", json={"refresh_token": tokens["refresh_token"]})

    assert response.status_code == 204
    assert (await refresh(client, tokens["refresh_token"])).status_code == 401


async def test_nfr_05_logout_without_a_session_still_succeeds(client: AsyncClient) -> None:
    assert (await client.post("/v1/auth/logout")).status_code == 204
    assert (
        await client.post("/v1/auth/logout", json={"refresh_token": "never-issued"})
    ).status_code == 204


# --- Browser transport: the refresh token lives in an httpOnly cookie ---


async def test_nfr_05_cookie_login_keeps_the_refresh_token_out_of_the_body(
    client: AsyncClient, make_user: MakeUser
) -> None:
    user = await make_user()

    response = await login(client, user, transport="cookie")

    assert response.json()["refresh_token"] is None
    cookie = response.headers["set-cookie"]
    assert cookie.startswith("refresh_token=")
    attributes = {part.strip().lower() for part in cookie.split(";")[1:]}
    assert {"httponly", "samesite=strict", "path=/v1/auth"} <= attributes
    # Local development runs over http; Secure is added outside it.
    assert "secure" not in attributes


async def test_nfr_05_cookie_is_secure_outside_local(
    client: AsyncClient,
    make_user: MakeUser,
    settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = await make_user()
    monkeypatch.setattr(settings, "environment", "production")

    response = await login(client, user, transport="cookie")

    assert "secure" in {part.strip().lower() for part in response.headers["set-cookie"].split(";")}


async def test_nfr_05_cookie_refresh_rotates_the_cookie(
    client: AsyncClient, make_user: MakeUser
) -> None:
    user = await make_user()
    await login(client, user, transport="cookie")
    first_cookie = client.cookies["refresh_token"]

    response = await client.post("/v1/auth/refresh", headers={"Origin": "http://localhost:8081"})

    assert response.status_code == 200
    assert response.json()["refresh_token"] is None
    assert client.cookies["refresh_token"] != first_cookie


async def test_nfr_05_cookie_refresh_from_another_origin_is_refused(
    client: AsyncClient, make_user: MakeUser
) -> None:
    user = await make_user()
    await login(client, user, transport="cookie")

    response = await client.post("/v1/auth/refresh", headers={"Origin": "https://evil.example"})

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "origin_not_allowed"


async def test_nfr_05_cookie_logout_clears_the_cookie_and_the_session(
    client: AsyncClient, make_user: MakeUser
) -> None:
    user = await make_user()
    await login(client, user, transport="cookie")
    cookie = client.cookies["refresh_token"]

    response = await client.post("/v1/auth/logout")

    assert response.status_code == 204
    assert "refresh_token" not in client.cookies
    assert (await refresh(client, cookie)).status_code == 401


async def test_cors_allows_the_web_app_origin_with_credentials(client: AsyncClient) -> None:
    response = await client.options(
        "/v1/auth/login",
        headers={
            "Origin": "http://localhost:8081",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:8081"
    assert response.headers["access-control-allow-credentials"] == "true"


async def test_cors_does_not_allow_other_origins(client: AsyncClient) -> None:
    response = await client.options(
        "/v1/auth/login",
        headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "POST"},
    )

    assert "access-control-allow-origin" not in response.headers
