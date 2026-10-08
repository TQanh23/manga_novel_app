import asyncio
import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from uuid import UUID

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

from api.core.config import get_settings

_JWT_ALGORITHM = "HS256"


class InvalidAccessTokenError(Exception):
    """The access token is malformed, expired or signed with another key."""


@lru_cache
def _hasher() -> PasswordHasher:
    settings = get_settings()
    return PasswordHasher(
        time_cost=settings.argon2_time_cost,
        memory_cost=settings.argon2_memory_cost_kib,
        parallelism=settings.argon2_parallelism,
    )


@lru_cache
def _dummy_hash() -> str:
    return _hasher().hash(secrets.token_urlsafe(16))


def _verify(password: str, password_hash: str) -> bool:
    try:
        return _hasher().verify(password_hash, password)
    except (VerificationError, InvalidHashError):
        return False


# argon2 is deliberately slow and CPU-bound, so it runs off the event loop.


async def hash_password(password: str) -> str:
    return await asyncio.to_thread(_hasher().hash, password)


async def verify_password(password: str, password_hash: str | None) -> bool:
    """Check a password. Pass None for an unknown account.

    An unknown account still costs one hash verification, so response time does
    not reveal whether an email is registered.
    """
    matches = await asyncio.to_thread(_verify, password, password_hash or _dummy_hash())
    return matches and password_hash is not None


def password_needs_rehash(password_hash: str) -> bool:
    return _hasher().check_needs_rehash(password_hash)


def create_access_token(user_id: UUID) -> tuple[str, int]:
    """Returns the token and its lifetime in seconds.

    The token only identifies the user. Roles and status are read from the
    database on every request, so locking an account takes effect at once.
    """
    settings = get_settings()
    now = datetime.now(UTC)
    ttl = settings.access_token_ttl_seconds
    token = jwt.encode(
        {
            "sub": str(user_id),
            "iat": now,
            "exp": now + timedelta(seconds=ttl),
            "jti": secrets.token_hex(8),
        },
        settings.jwt_secret.get_secret_value(),
        algorithm=_JWT_ALGORITHM,
    )
    return token, ttl


def decode_access_token(token: str) -> UUID:
    try:
        claims = jwt.decode(
            token,
            get_settings().jwt_secret.get_secret_value(),
            algorithms=[_JWT_ALGORITHM],
            options={"require": ["exp", "sub"]},
        )
        return UUID(claims["sub"])
    except (jwt.InvalidTokenError, ValueError) as exc:
        raise InvalidAccessTokenError from exc


def new_refresh_token() -> tuple[str, str]:
    """Returns an opaque token for the client and the hash the database stores."""
    token = secrets.token_urlsafe(32)
    return token, hash_refresh_token(token)


def hash_refresh_token(token: str) -> str:
    # The token is 256 random bits, so a fast hash is enough to make a leaked
    # table useless; there is nothing to brute-force.
    return hashlib.sha256(token.encode()).hexdigest()
