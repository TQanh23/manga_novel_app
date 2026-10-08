"""FR-AD-01: an admin locks accounts and assigns roles. FR-AUTH-03: only admins may."""

from uuid import uuid4

import pytest
from httpx import AsyncClient

from api.auth.models import Role
from api.testing import TEST_PASSWORD, AuthHeaders, MakeUser


async def test_fr_ad_01_admin_locks_a_user_and_ends_their_sessions(
    client: AsyncClient, make_user: MakeUser, auth_headers: AuthHeaders
) -> None:
    admin, reader = await make_user(Role.ADMIN), await make_user()
    tokens = (
        await client.post("/v1/auth/login", json={"email": reader.email, "password": TEST_PASSWORD})
    ).json()

    response = await client.patch(
        f"/v1/admin/users/{reader.id}", json={"status": "locked"}, headers=auth_headers(admin)
    )

    assert response.status_code == 200
    assert response.json()["status"] == "locked"
    assert response.json()["roles"] == ["reader"]

    login = await client.post(
        "/v1/auth/login", json={"email": reader.email, "password": TEST_PASSWORD}
    )
    me = await client.get("/v1/me", headers={"Authorization": f"Bearer {tokens['access_token']}"})
    refreshed = await client.post(
        "/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
    )
    assert login.status_code == 403
    assert me.status_code == 403
    assert refreshed.status_code == 401


async def test_fr_ad_01_admin_unlocks_a_user(
    client: AsyncClient, make_user: MakeUser, auth_headers: AuthHeaders
) -> None:
    admin, reader = await make_user(Role.ADMIN), await make_user()
    await client.patch(
        f"/v1/admin/users/{reader.id}", json={"status": "locked"}, headers=auth_headers(admin)
    )

    response = await client.patch(
        f"/v1/admin/users/{reader.id}", json={"status": "active"}, headers=auth_headers(admin)
    )

    assert response.json()["status"] == "active"
    login = await client.post(
        "/v1/auth/login", json={"email": reader.email, "password": TEST_PASSWORD}
    )
    assert login.status_code == 200


async def test_fr_ad_01_admin_sets_a_users_roles(
    client: AsyncClient, make_user: MakeUser, auth_headers: AuthHeaders
) -> None:
    admin, user = await make_user(Role.ADMIN), await make_user(Role.READER, Role.AUTHOR)

    promoted = await client.patch(
        f"/v1/admin/users/{user.id}",
        json={"roles": ["reader", "admin"]},
        headers=auth_headers(admin),
    )

    assert promoted.status_code == 200
    assert promoted.json()["roles"] == ["admin", "reader"]
    assert promoted.json()["status"] == "active"
    # The change is live for the user's existing access token.
    as_new_admin = await client.patch(
        f"/v1/admin/users/{admin.id}", json={}, headers=auth_headers(user)
    )
    assert as_new_admin.status_code == 200


@pytest.mark.parametrize("roles", [(Role.READER,), (Role.READER, Role.AUTHOR)])
async def test_fr_auth_03_non_admins_get_403(
    client: AsyncClient, make_user: MakeUser, auth_headers: AuthHeaders, roles: tuple[Role, ...]
) -> None:
    caller, target = await make_user(*roles), await make_user()

    response = await client.patch(
        f"/v1/admin/users/{target.id}", json={"status": "locked"}, headers=auth_headers(caller)
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden"


async def test_fr_auth_03_admin_routes_require_sign_in(client: AsyncClient) -> None:
    response = await client.patch(f"/v1/admin/users/{uuid4()}", json={"status": "locked"})

    assert response.status_code == 401


async def test_fr_ad_01_an_admin_cannot_lock_or_demote_themselves(
    client: AsyncClient, make_user: MakeUser, auth_headers: AuthHeaders
) -> None:
    admin = await make_user(Role.ADMIN)

    locked = await client.patch(
        f"/v1/admin/users/{admin.id}", json={"status": "locked"}, headers=auth_headers(admin)
    )
    demoted = await client.patch(
        f"/v1/admin/users/{admin.id}", json={"roles": ["reader"]}, headers=auth_headers(admin)
    )

    assert (locked.status_code, locked.json()["error"]["code"]) == (409, "cannot_lock_self")
    assert (demoted.status_code, demoted.json()["error"]["code"]) == (409, "cannot_demote_self")
    assert (await client.get("/v1/me", headers=auth_headers(admin))).json()["roles"] == ["admin"]


async def test_fr_ad_01_unknown_user_is_404(
    client: AsyncClient, make_user: MakeUser, auth_headers: AuthHeaders
) -> None:
    admin = await make_user(Role.ADMIN)

    response = await client.patch(
        f"/v1/admin/users/{uuid4()}", json={"status": "locked"}, headers=auth_headers(admin)
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "user_not_found"


@pytest.mark.parametrize("payload", [{"roles": []}, {"roles": ["editor"]}, {"status": "deleted"}])
async def test_fr_ad_01_invalid_updates_are_rejected(
    client: AsyncClient,
    make_user: MakeUser,
    auth_headers: AuthHeaders,
    payload: dict[str, object],
) -> None:
    admin, user = await make_user(Role.ADMIN), await make_user()

    response = await client.patch(
        f"/v1/admin/users/{user.id}", json=payload, headers=auth_headers(admin)
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
