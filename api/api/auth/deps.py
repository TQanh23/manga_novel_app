from collections.abc import Awaitable, Callable
from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import service
from api.auth.models import Role, User
from api.core.db import get_session
from api.core.errors import AppError
from api.core.rate_limit import limit_by_identity

_bearer = HTTPBearer(auto_error=False)

Session = Annotated[AsyncSession, Depends(get_session)]


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    session: Session,
) -> User:
    if credentials is None:
        raise AppError(
            "unauthenticated",
            "Sign in to continue",
            status_code=401,
            headers={"WWW-Authenticate": "Bearer"},
        )
    return await service.authenticate(session, credentials.credentials)


CurrentUser = Annotated[User, Depends(get_current_user)]


async def get_optional_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    session: Session,
) -> User | None:
    """The signed-in account, or None for a guest.

    A token that is sent has to be valid: an expired one gets 401, so the
    client refreshes it instead of silently reading as a guest.
    """
    if credentials is None:
        return None
    return await service.authenticate(session, credentials.credentials)


OptionalUser = Annotated[User | None, Depends(get_optional_user)]


def require_role(*roles: Role) -> Callable[[User], Awaitable[User]]:
    """Route dependency: the caller must hold at least one of the roles."""

    async def dependency(user: CurrentUser) -> User:
        if not any(user.has_role(role) for role in roles):
            raise AppError("forbidden", "You do not have access to this resource", status_code=403)
        return user

    return dependency


def limit_by_user(
    scope: str, *, limit: Callable[[], int] | None = None
) -> Callable[[User], Awaitable[None]]:
    """Route dependency: rate limit by the signed-in account.

    `limit` is read on each request, so it can come from settings. Without it
    the auth limit applies.
    """

    async def dependency(user: CurrentUser) -> None:
        await limit_by_identity(scope, str(user.id), limit=limit() if limit else None)

    return dependency
