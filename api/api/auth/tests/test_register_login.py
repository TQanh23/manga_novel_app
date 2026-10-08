"""FR-AUTH-01: email and password sign-up and sign-in. NFR-05: argon2, short-lived JWT."""

import pytest
from argon2 import PasswordHasher
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth.models import User
from api.core.config import Settings
from api.testing import TEST_PASSWORD, AuthHeaders, MakeUser

REGISTRATION = {
    "email": "Reader@Example.com",
    "password": TEST_PASSWORD,
    "display_name": "  Nguyễn Văn A  ",
    "locale": "vi",
}


async def test_fr_auth_01_register_creates_an_active_reader(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    response = await client.post("/v1/auth/register", json=REGISTRATION)

    assert response.status_code == 201
    body = response.json()
    assert body == {
        "id": body["id"],
        "email": "reader@example.com",
        "display_name": "Nguyễn Văn A",
        "locale": "vi",
        "status": "active",
        "roles": ["reader"],
    }
    assert TEST_PASSWORD not in response.text


async def test_nfr_05_password_is_stored_as_an_argon2id_hash(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    await client.post("/v1/auth/register", json=REGISTRATION)

    user = (await db_session.execute(select(User))).scalar_one()
    assert user.password_hash.startswith("$argon2id$")
    assert TEST_PASSWORD not in user.password_hash


@pytest.mark.parametrize(
    "display_name", ["Trần Thị Bích Ngọc", "김민준", "佐藤 さくら", "Zoë O'Brien"]
)
async def test_fr_auth_01_display_names_keep_non_ascii_text(
    client: AsyncClient, display_name: str
) -> None:
    response = await client.post(
        "/v1/auth/register", json={**REGISTRATION, "display_name": display_name}
    )

    assert response.status_code == 201
    assert response.json()["display_name"] == display_name


async def test_fr_auth_01_an_email_can_only_register_once_whatever_its_case(
    client: AsyncClient,
) -> None:
    await client.post("/v1/auth/register", json=REGISTRATION)

    response = await client.post(
        "/v1/auth/register", json={**REGISTRATION, "email": "READER@example.com"}
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "email_taken"


@pytest.mark.parametrize(
    ("field", "value", "error_type"),
    [
        ("password", "hunter2", "too_short"),
        ("password", "x" * 129, "too_long"),
        ("email", "not-an-email", "value_error"),
        ("display_name", "   ", "string_too_short"),
        ("display_name", "가" * 81, "string_too_long"),
        ("locale", "fr", "enum"),
    ],
)
async def test_fr_auth_01_register_rejects_invalid_input_without_echoing_it(
    client: AsyncClient, field: str, value: str, error_type: str
) -> None:
    response = await client.post("/v1/auth/register", json={**REGISTRATION, field: value})

    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "validation_error"
    assert [(detail["loc"], detail["type"]) for detail in error["details"]] == [
        (["body", field], error_type)
    ]
    assert value not in response.text


async def test_fr_auth_01_login_returns_tokens_and_the_user(
    client: AsyncClient, make_user: MakeUser, settings: Settings
) -> None:
    user = await make_user(email="reader@example.com")

    response = await client.post(
        "/v1/auth/login", json={"email": "Reader@Example.com", "password": TEST_PASSWORD}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["expires_in"] == settings.access_token_ttl_seconds == 900
    assert body["refresh_token"]
    assert body["user"]["id"] == str(user.id)
    assert body["user"]["roles"] == ["reader"]
    assert "set-cookie" not in response.headers

    me = await client.get("/v1/me", headers={"Authorization": f"Bearer {body['access_token']}"})
    assert me.status_code == 200
    assert me.json() == body["user"]


async def test_fr_auth_01_wrong_password_and_unknown_email_look_the_same(
    client: AsyncClient, make_user: MakeUser
) -> None:
    await make_user(email="reader@example.com")

    wrong_password = await client.post(
        "/v1/auth/login", json={"email": "reader@example.com", "password": "not the password"}
    )
    unknown_email = await client.post(
        "/v1/auth/login", json={"email": "nobody@example.com", "password": TEST_PASSWORD}
    )

    assert wrong_password.status_code == unknown_email.status_code == 401
    assert wrong_password.json()["error"]["code"] == "invalid_credentials"
    assert {**wrong_password.json()["error"], "request_id": None} == {
        **unknown_email.json()["error"],
        "request_id": None,
    }


async def test_nfr_05_login_upgrades_a_hash_made_with_older_parameters(
    client: AsyncClient, make_user: MakeUser, db_session: AsyncSession
) -> None:
    user = await make_user()
    old_hash = PasswordHasher(time_cost=2, memory_cost=32, parallelism=1).hash(TEST_PASSWORD)
    user.password_hash = old_hash
    await db_session.commit()

    response = await client.post(
        "/v1/auth/login", json={"email": user.email, "password": TEST_PASSWORD}
    )

    assert response.status_code == 200
    assert user.password_hash != old_hash
    assert "$m=64,t=1,p=1$" in user.password_hash


async def test_nfr_05_me_requires_a_token(client: AsyncClient) -> None:
    response = await client.get("/v1/me")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthenticated"
    assert response.headers["WWW-Authenticate"] == "Bearer"


@pytest.mark.parametrize("token", ["garbage", "a.b.c", ""])
async def test_nfr_05_me_rejects_a_malformed_token(client: AsyncClient, token: str) -> None:
    response = await client.get("/v1/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 401
    assert response.json()["error"]["code"] in {"invalid_token", "unauthenticated"}


async def test_nfr_05_an_expired_access_token_is_rejected(
    client: AsyncClient,
    make_user: MakeUser,
    auth_headers: AuthHeaders,
    settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = await make_user()
    monkeypatch.setattr(settings, "access_token_ttl_seconds", -1)

    response = await client.get("/v1/me", headers=auth_headers(user))

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_token"


async def test_nfr_05_a_token_signed_with_another_key_is_rejected(
    client: AsyncClient,
    make_user: MakeUser,
    auth_headers: AuthHeaders,
    settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = await make_user()
    headers = auth_headers(user)
    monkeypatch.setattr(settings, "jwt_secret", type(settings.jwt_secret)("another-key-" * 4))

    response = await client.get("/v1/me", headers=headers)

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_token"
