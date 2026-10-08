from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, Field

from api.auth.models import Role, UserStatus


class AdminUserUpdate(BaseModel):
    """Fields left out stay as they are."""

    status: UserStatus | None = None
    # The complete set of roles the account should hold afterwards.
    roles: Annotated[list[Role], Field(min_length=1)] | None = None


class JobAccepted(BaseModel):
    """Body of a 202: the work was queued, not done."""

    job_id: UUID
