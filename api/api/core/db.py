from collections.abc import AsyncIterator
from functools import lru_cache
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from api.core.config import get_settings


@lru_cache
def get_engine() -> AsyncEngine:
    # hide_parameters keeps bound values (manuscript text, emails, hashes) out of
    # SQLAlchemy's log lines and exception messages.
    return create_async_engine(
        get_settings().database_url, pool_pre_ping=True, hide_parameters=True
    )


@lru_cache
def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(get_engine(), expire_on_commit=False)


async def set_author_context(session: AsyncSession, author_id: UUID) -> None:
    """Scope the current transaction to one author's drafts.

    Row-level security on author-private tables compares each row's author_id
    with this setting. It lasts until the transaction ends, so every
    transaction that reads or writes drafts sets it again.
    """
    await session.execute(
        text("SELECT set_config('app.author_id', :author_id, true)"),
        {"author_id": str(author_id)},
    )


async def get_session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency. Services own the transaction; nothing commits here."""
    async with get_sessionmaker()() as session:
        yield session
