from datetime import datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth.models import RefreshToken, User


async def get_user(session: AsyncSession, user_id: UUID) -> User | None:
    # populate_existing: always the row as it is now, never a copy the session
    # already holds, because status and roles gate every request.
    return await session.get(User, user_id, populate_existing=True)


async def get_user_by_email(session: AsyncSession, email: str) -> User | None:
    result = await session.execute(
        select(User).where(User.email == email).execution_options(populate_existing=True)
    )
    return result.scalar_one_or_none()


def add_refresh_token(
    session: AsyncSession, *, user_id: UUID, family_id: UUID, token_hash: str, expires_at: datetime
) -> None:
    session.add(
        RefreshToken(
            user_id=user_id, family_id=family_id, token_hash=token_hash, expires_at=expires_at
        )
    )


async def get_refresh_token(
    session: AsyncSession, token_hash: str, *, for_update: bool = False
) -> RefreshToken | None:
    statement = (
        select(RefreshToken)
        .where(RefreshToken.token_hash == token_hash)
        .execution_options(populate_existing=True)
    )
    if for_update:
        # Two requests carrying the same token queue here, so only the first
        # sees it unused.
        statement = statement.with_for_update()
    return (await session.execute(statement)).scalar_one_or_none()


async def revoke_family(session: AsyncSession, family_id: UUID, now: datetime) -> None:
    await session.execute(
        update(RefreshToken)
        .where(RefreshToken.family_id == family_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=now)
    )


async def revoke_all_for_user(session: AsyncSession, user_id: UUID, now: datetime) -> None:
    await session.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=now)
    )
