"""NFR-05: argon2 password hashing, signed short-lived access tokens, opaque refresh tokens."""

from uuid import uuid4

import pytest
from pydantic import SecretStr, ValidationError

from api.core.config import Settings
from api.core.security import (
    InvalidAccessTokenError,
    create_access_token,
    decode_access_token,
    hash_password,
    hash_refresh_token,
    new_refresh_token,
    password_needs_rehash,
    verify_password,
)

pytestmark = pytest.mark.usefixtures("settings")


async def test_a_password_verifies_against_its_own_hash_only() -> None:
    password_hash = await hash_password("mật khẩu của tôi")

    assert await verify_password("mật khẩu của tôi", password_hash)
    assert not await verify_password("mat khau cua toi", password_hash)


async def test_hashes_are_salted() -> None:
    assert await hash_password("same password") != await hash_password("same password")


async def test_an_unknown_account_never_verifies() -> None:
    assert not await verify_password("anything", None)


async def test_a_corrupt_hash_fails_closed() -> None:
    assert not await verify_password("anything", "not-a-hash")


async def test_a_fresh_hash_does_not_need_rehashing() -> None:
    assert not password_needs_rehash(await hash_password("some password"))


def test_an_access_token_round_trips_to_its_user() -> None:
    user_id = uuid4()

    token, ttl = create_access_token(user_id)

    assert decode_access_token(token) == user_id
    assert ttl > 0


def test_a_tampered_access_token_is_rejected() -> None:
    token, _ = create_access_token(uuid4())
    header, payload, signature = token.split(".")
    other_payload = create_access_token(uuid4())[0].split(".")[1]

    with pytest.raises(InvalidAccessTokenError):
        decode_access_token(f"{header}.{other_payload}.{signature}")
    assert payload != other_payload


def test_an_unsigned_token_is_rejected() -> None:
    import jwt

    token = jwt.encode({"sub": str(uuid4()), "exp": 4102444800}, "", algorithm="none")

    with pytest.raises(InvalidAccessTokenError):
        decode_access_token(token)


def test_refresh_tokens_are_random_and_stored_hashed() -> None:
    token, token_hash = new_refresh_token()
    other_token, _ = new_refresh_token()

    assert token != other_token
    assert token_hash == hash_refresh_token(token)
    assert token not in token_hash


def test_dev_jwt_secret_is_refused_outside_local() -> None:
    with pytest.raises(ValidationError, match="JWT_SECRET must be set"):
        Settings(environment="production")


def test_production_settings_turn_on_secure_cookies() -> None:
    production = Settings(environment="production", jwt_secret=SecretStr("k" * 48))

    assert production.cookie_secure
    assert not Settings(environment="local").cookie_secure
