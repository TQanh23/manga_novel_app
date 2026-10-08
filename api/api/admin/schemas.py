from typing import Annotated

from pydantic import BaseModel, Field

from api.auth.models import Role, UserStatus


class AdminUserUpdate(BaseModel):
    """Fields left out stay as they are."""

    status: UserStatus | None = None
    # The complete set of roles the account should hold afterwards.
    roles: Annotated[list[Role], Field(min_length=1)] | None = None
