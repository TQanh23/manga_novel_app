"""FR-AUTH-03: roles. FR-AD-01 (effect on the user): a locked account is shut out at once."""

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth.models import Role, UserStatus
from api.testing import TEST_PASSWORD, AuthHeaders, MakeUser


async def test_fr_auth_03_a_reader_can_become_an_author_and_keeps_reader(
    client: AsyncClient, make_user: MakeUser, auth_headers: AuthHeaders
) -> None:
    user = await make_user()

    response = await client.post("/v1/me/roles/author", headers=auth_headers(user))

    assert response.status_code == 200
    assert response.json()["roles"] == ["author", "reader"]
    me = await client.get("/v1/me", headers=auth_headers(user))
    assert me.json()["roles"] == ["author", "reader"]


async def test_fr_auth_03_becoming_an_author_twice_changes_nothing(
    client: AsyncClient, make_user: MakeUser, auth_headers: AuthHeaders
) -> None:
    user = await make_user()
    await client.post("/v1/me/roles/author", headers=auth_headers(user))

    response = await client.post("/v1/me/roles/author", headers=auth_headers(user))

    assert response.status_code == 200
    assert response.json()["roles"] == ["author", "reader"]


async def test_fr_auth_03_becoming_an_author_requires_sign_in(client: AsyncClient) -> None:
    response = await client.post("/v1/me/roles/author")

    assert response.status_code == 401


async def test_fr_ad_01_a_locked_user_cannot_log_in(
    client: AsyncClient, make_user: MakeUser, db_session: AsyncSession
) -> None:
    user = await make_user()
    user.status = UserStatus.LOCKED
    await db_session.commit()

    response = await client.post(
        "/v1/auth/login", json={"email": user.email, "password": TEST_PASSWORD}
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "account_locked"


async def test_fr_ad_01_locking_does_not_reveal_itself_to_a_wrong_password(
    client: AsyncClient, make_user: MakeUser, db_session: AsyncSession
) -> None:
    user = await make_user()
    user.status = UserStatus.LOCKED
    await db_session.commit()

    response = await client.post(
        "/v1/auth/login", json={"email": user.email, "password": "not the password"}
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_credentials"


async def test_fr_ad_01_a_locked_users_tokens_stop_working_at_once(
    client: AsyncClient, make_user: MakeUser, db_session: AsyncSession
) -> None:
    user = await make_user(Role.READER, Role.AUTHOR)
    tokens = (
        await client.post("/v1/auth/login", json={"email": user.email, "password": TEST_PASSWORD})
    ).json()
    user.status = UserStatus.LOCKED
    await db_session.commit()

    me = await client.get("/v1/me", headers={"Authorization": f"Bearer {tokens['access_token']}"})
    refreshed = await client.post(
        "/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
    )

    assert me.status_code == 403
    assert me.json()["error"]["code"] == "account_locked"
    assert refreshed.status_code == 403
    assert refreshed.json()["error"]["code"] == "account_locked"
