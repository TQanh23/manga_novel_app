from collections.abc import Sequence
from datetime import UTC, datetime
from uuid import UUID

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import repository as auth_repository
from api.auth.models import Role, User, UserRole, UserStatus
from api.core.errors import AppError
from api.core.ids import uuid7
from api.core.queue import enqueue

logger = structlog.get_logger(__name__)


async def enqueue_ping(session: AsyncSession, *, actor: User) -> UUID:
    """Queue a job that does nothing, to prove the API can reach the worker."""
    # A ping has no input to hash, so each one is its own job.
    return await enqueue(session, kind="ping", target_id=actor.id, content_hash=uuid7().hex)


async def update_user(
    session: AsyncSession,
    *,
    actor: User,
    user_id: UUID,
    status: UserStatus | None,
    roles: Sequence[Role] | None,
) -> User:
    """Lock or unlock an account and set its roles (FR-AD-01)."""
    user = await auth_repository.get_user(session, user_id)
    if user is None:
        raise AppError("user_not_found", "User not found", status_code=404)

    # An admin who locks or demotes themselves cannot undo it, and if they were
    # the last admin nobody could.
    if user.id == actor.id:
        if status == UserStatus.LOCKED:
            raise AppError("cannot_lock_self", "You cannot lock your own account", status_code=409)
        if roles is not None and Role.ADMIN not in roles:
            raise AppError(
                "cannot_demote_self", "You cannot remove your own admin role", status_code=409
            )

    if roles is not None:
        wanted = set(roles)
        held = {role.role for role in user.roles}
        user.roles = [role for role in user.roles if role.role in wanted] + [
            UserRole(role=role) for role in sorted(wanted - held)
        ]

    if status is not None and status != user.status:
        user.status = status
        if status == UserStatus.LOCKED:
            # Access tokens die on the next request (status is read each time);
            # this ends the sessions that could mint new ones.
            await auth_repository.revoke_all_for_user(session, user.id, datetime.now(UTC))

    await session.commit()
    logger.info(
        "admin_user_updated",
        actor_id=str(actor.id),
        user_id=str(user.id),
        status=user.status,
        roles=user.role_names,
    )
    return user
