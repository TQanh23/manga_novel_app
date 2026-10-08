"""Create the development accounts: one admin, one author, two readers.

    uv run python -m api.scripts.seed

Runs on `docker compose up`. Safe to run again: an account that already exists
is left exactly as it is. The accounts share a password that is in the
repository, so this refuses to run anywhere but a local environment.
"""

import asyncio
from dataclasses import dataclass

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import repository, service
from api.auth.models import Locale, Role
from api.core.config import get_settings
from api.core.db import get_engine, get_sessionmaker
from api.core.logging import configure_logging

logger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class SeedAccount:
    email: str
    display_name: str
    roles: tuple[Role, ...]
    locale: Locale = Locale.EN


SEED_ACCOUNTS = (
    SeedAccount("admin@example.com", "Admin", (Role.ADMIN,)),
    SeedAccount("author@example.com", "Nguyễn Tác Giả", (Role.READER, Role.AUTHOR), Locale.VI),
    SeedAccount("reader1@example.com", "Reader One", (Role.READER,)),
    SeedAccount("reader2@example.com", "Độc Giả Hai", (Role.READER,), Locale.VI),
)


async def seed(session: AsyncSession) -> list[str]:
    """Create the accounts that are missing. Returns the emails it created."""
    settings = get_settings()
    if settings.environment != "local":
        raise RuntimeError("Seed accounts have a public password; refusing to create them here.")

    created = []
    for account in SEED_ACCOUNTS:
        if await repository.get_user_by_email(session, account.email) is not None:
            continue
        await service.register(
            session,
            email=account.email,
            password=settings.seed_password.get_secret_value(),
            display_name=account.display_name,
            locale=account.locale,
            roles=account.roles,
        )
        created.append(account.email)
    return created


async def _main() -> None:
    configure_logging(get_settings().log_level)
    try:
        async with get_sessionmaker()() as session:
            created = await seed(session)
    finally:
        await get_engine().dispose()
    logger.info("seed_finished", created=len(created), existing=len(SEED_ACCOUNTS) - len(created))


if __name__ == "__main__":
    asyncio.run(_main())
