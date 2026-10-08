from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, SecretStr, StringConstraints

from api.auth.models import Locale, Role, User, UserStatus

# Length is counted in characters, so Korean, Japanese and Vietnamese names get
# the same room as ASCII ones.
DisplayName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]
# The upper bound keeps a huge password from tying up the argon2 thread pool.
Password = Annotated[SecretStr, Field(min_length=8, max_length=128)]


class RegisterRequest(BaseModel):
    email: EmailStr
    password: Password
    display_name: DisplayName
    locale: Locale = Locale.EN


class LoginRequest(BaseModel):
    email: EmailStr
    password: Annotated[SecretStr, Field(min_length=1, max_length=128)]
    # "cookie" is for browsers: the refresh token is set as an httpOnly cookie
    # and never appears in a response body, where page scripts could read it.
    token_transport: Literal["body", "cookie"] = "body"  # noqa: S105


class RefreshRequest(BaseModel):
    # Omitted by browsers, which send the cookie instead.
    refresh_token: str | None = None


class UserResponse(BaseModel):
    id: UUID
    email: str
    display_name: str
    locale: Locale
    status: UserStatus
    roles: list[Role]

    @classmethod
    def from_user(cls, user: User) -> "UserResponse":
        return cls(
            id=user.id,
            email=user.email,
            display_name=user.display_name,
            locale=Locale(user.locale),
            status=UserStatus(user.status),
            roles=[Role(name) for name in user.role_names],
        )


class TokenResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"  # noqa: S105
    expires_in: int
    # null when the refresh token travelled in the cookie.
    refresh_token: str | None
    user: UserResponse
