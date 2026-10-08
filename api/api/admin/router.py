from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status

from api.admin import service
from api.admin.schemas import AdminUserUpdate, JobAccepted
from api.auth.deps import Session, require_role
from api.auth.models import Role, User
from api.auth.schemas import UserResponse

router = APIRouter(prefix="/admin", tags=["admin"])

Admin = Annotated[User, Depends(require_role(Role.ADMIN))]


@router.post("/jobs/ping", operation_id="admin_enqueue_ping", status_code=status.HTTP_202_ACCEPTED)
async def enqueue_ping(actor: Admin, session: Session) -> JobAccepted:
    return JobAccepted(job_id=await service.enqueue_ping(session, actor=actor))


@router.patch("/users/{user_id}", operation_id="admin_update_user")
async def update_user(
    user_id: UUID, payload: AdminUserUpdate, actor: Admin, session: Session
) -> UserResponse:
    user = await service.update_user(
        session, actor=actor, user_id=user_id, status=payload.status, roles=payload.roles
    )
    return UserResponse.from_user(user)
