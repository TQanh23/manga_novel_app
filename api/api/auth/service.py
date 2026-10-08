from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

import structlog
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import repository
from api.auth.models import Locale, Role, User, UserRole, UserStatus
from api.core.config import get_settings
from api.core.errors import AppError
from api.core.ids import uuid7
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

logger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class IssuedTokens:
    user: User
    access_token: str
    expires_in: int
    refresh_token: str


def _email_taken() -> AppError:
    return AppError("email_taken", "An account with this email already exists", status_code=409)


def _invalid_credentials() -> AppError:
    # One error for an unknown email and for a wrong password.
    return AppError("invalid_credentials", "Email or password is incorrect", status_code=401)


def _account_locked() -> AppError:
    return AppError("account_locked", "This account is locked", status_code=403)


def _invalid_refresh_token() -> AppError:
    return AppError("invalid_refresh_token", "Sign in again", status_code=401)


def _invalid_access_token() -> AppError:
    return AppError(
        "invalid_token",
        "Access token is invalid or expired",
        status_code=401,
        headers={"WWW-Authenticate": "Bearer"},
    )


def normalize_email(email: str) -> str:
    return email.strip().lower()


async def register(
    session: AsyncSession,
    *,
    email: str,
    password: str,
    display_name: str,
    locale: Locale = Locale.EN,
    roles: Iterable[Role] = (Role.READER,),
) -> User:
    """Create an account (FR-AUTH-01). Public sign-up always passes the default role."""
    email = normalize_email(email)
    if await repository.get_user_by_email(session, email) is not None:
        raise _email_taken()

    user = User(
        email=email,
        password_hash=await hash_password(password),
        display_name=display_name,
        locale=locale,
        roles=[UserRole(role=role) for role in dict.fromkeys(roles)],
    )
    session.add(user)
    try:
        await session.commit()
    except IntegrityError:
        # Lost a race with another sign-up for the same address.
        await session.rollback()
        raise _email_taken() from None

    logger.info("user_registered", user_id=str(user.id))
    return user


def _issue_tokens(session: AsyncSession, user: User, family_id: UUID) -> IssuedTokens:
    access_token, expires_in = create_access_token(user.id)
    refresh_token, token_hash = new_refresh_token()
    repository.add_refresh_token(
        session,
        user_id=user.id,
        family_id=family_id,
        token_hash=token_hash,
        expires_at=datetime.now(UTC) + timedelta(seconds=get_settings().refresh_token_ttl_seconds),
    )
    return IssuedTokens(user, access_token, expires_in, refresh_token)


async def login(session: AsyncSession, *, email: str, password: str) -> IssuedTokens:
    user = await repository.get_user_by_email(session, normalize_email(email))
    password_matches = await verify_password(password, user.password_hash if user else None)
    if user is None or not password_matches:
        raise _invalid_credentials()
    # Only reported once the password is known to be right, so it cannot be
    # used to probe which emails are registered.
    if user.status == UserStatus.LOCKED:
        raise _account_locked()

    if password_needs_rehash(user.password_hash):
        user.password_hash = await hash_password(password)

    tokens = _issue_tokens(session, user, family_id=uuid7())
    await session.commit()
    logger.info("user_logged_in", user_id=str(user.id))
    return tokens


async def refresh(session: AsyncSession, *, refresh_token: str) -> IssuedTokens:
    """Trade a refresh token for a new pair. Each token works once."""
    now = datetime.now(UTC)
    row = await repository.get_refresh_token(
        session, hash_refresh_token(refresh_token), for_update=True
    )
    if row is None or row.revoked_at is not None or row.expires_at <= now:
        raise _invalid_refresh_token()

    if row.used_at is not None:
        grace = timedelta(seconds=get_settings().refresh_reuse_grace_seconds)
        if now - row.used_at <= grace:
            raise AppError(
                "refresh_conflict",
                "This session was just refreshed by another request",
                status_code=409,
            )
        # A spent token coming back later means it was copied. Whoever holds
        # the newest one may be the thief, so the whole session ends.
        await repository.revoke_family(session, row.family_id, now)
        await session.commit()
        logger.warning(
            "refresh_token_reuse", user_id=str(row.user_id), family_id=str(row.family_id)
        )
        raise _invalid_refresh_token()

    user = await repository.get_user(session, row.user_id)
    if user is None:
        raise _invalid_refresh_token()
    if user.status == UserStatus.LOCKED:
        await repository.revoke_family(session, row.family_id, now)
        await session.commit()
        raise _account_locked()

    row.used_at = now
    tokens = _issue_tokens(session, user, family_id=row.family_id)
    await session.commit()
    return tokens


async def logout(session: AsyncSession, *, refresh_token: str | None) -> None:
    """End the session the token belongs to. Unknown tokens are ignored."""
    if not refresh_token:
        return
    row = await repository.get_refresh_token(session, hash_refresh_token(refresh_token))
    if row is None:
        return
    await repository.revoke_family(session, row.family_id, datetime.now(UTC))
    await session.commit()


async def authenticate(session: AsyncSession, access_token: str) -> User:
    """Resolve an access token to an active user, reading the user fresh from the database."""
    try:
        user_id = decode_access_token(access_token)
    except InvalidAccessTokenError:
        raise _invalid_access_token() from None

    user = await repository.get_user(session, user_id)
    if user is None:
        raise _invalid_access_token()
    if user.status == UserStatus.LOCKED:
        raise _account_locked()
    return user


async def add_author_role(session: AsyncSession, user: User) -> User:
    """Let a reader start writing (decision D12). Calling it again changes nothing."""
    if user.has_role(Role.AUTHOR):
        return user

    user.roles.append(UserRole(role=Role.AUTHOR))
    try:
        await session.commit()
    except IntegrityError:
        # A concurrent request added the role first.
        await session.rollback()
        refreshed = await repository.get_user(session, user.id)
        if refreshed is None:
            raise _invalid_access_token() from None
        return refreshed

    logger.info("author_role_added", user_id=str(user.id))
    return user
