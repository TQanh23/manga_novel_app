from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from api.author import service as author_service
from worker.runtime import cron

NAME = "publish-scheduled"


@cron(NAME)
async def publish_scheduled(sessions: async_sessionmaker[AsyncSession]) -> None:
    """Every minute: scheduled episodes whose time has come go live (FR-NV-02)."""
    async with sessions() as session:
        await author_service.publish_due_episodes(session)
