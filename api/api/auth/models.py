from datetime import datetime
from enum import StrEnum
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from api.core.models import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Role(StrEnum):
    READER = "reader"
    AUTHOR = "author"
    ADMIN = "admin"


class UserStatus(StrEnum):
    ACTIVE = "active"
    LOCKED = "locked"


class Locale(StrEnum):
    EN = "en"
    VI = "vi"


def _one_of(column: str, values: type[StrEnum]) -> str:
    return f"{column} IN ({', '.join(repr(str(value)) for value in values)})"


class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """An account. All personal data lives in this table (FR-AUTH-05)."""

    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("email"),
        # The service lowercases emails; this stops any other writer from
        # creating a second account that differs only by case.
        CheckConstraint("email = lower(email)", name="email_lowercase"),
        CheckConstraint(_one_of("locale", Locale), name="locale"),
        CheckConstraint(_one_of("status", UserStatus), name="status"),
        {"schema": "core"},
    )

    email: Mapped[str] = mapped_column(Text)
    password_hash: Mapped[str] = mapped_column(Text)
    display_name: Mapped[str] = mapped_column(Text)
    locale: Mapped[str] = mapped_column(Text, default=Locale.EN, server_default=Locale.EN)
    status: Mapped[str] = mapped_column(
        Text, default=UserStatus.ACTIVE, server_default=UserStatus.ACTIVE
    )

    roles: Mapped[list["UserRole"]] = relationship(
        lazy="selectin", cascade="all, delete-orphan", passive_deletes=True
    )

    @property
    def role_names(self) -> list[str]:
        return sorted(role.role for role in self.roles)

    def has_role(self, role: Role) -> bool:
        return any(held.role == role for held in self.roles)


class UserRole(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One role held by one account. An account can hold several (FR-AUTH-03)."""

    __tablename__ = "user_roles"
    __table_args__ = (
        UniqueConstraint("user_id", "role"),
        # Text plus a check, not a Postgres enum: adding a role later is a
        # one-line constraint change instead of ALTER TYPE.
        CheckConstraint(_one_of("role", Role), name="role"),
        {"schema": "core"},
    )

    user_id: Mapped[UUID] = mapped_column(ForeignKey("core.users.id", ondelete="CASCADE"))
    role: Mapped[str] = mapped_column(Text)


class RefreshToken(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One link in a rotation chain. Only the hash of the token is stored."""

    __tablename__ = "refresh_tokens"
    __table_args__ = (UniqueConstraint("token_hash"), {"schema": "core"})

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("core.users.id", ondelete="CASCADE"), index=True
    )
    # Every token descended from one login shares a family, so the whole
    # session can be revoked when one of them is replayed.
    family_id: Mapped[UUID] = mapped_column(index=True)
    token_hash: Mapped[str] = mapped_column(Text)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
