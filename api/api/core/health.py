import asyncio
from collections.abc import Awaitable, Callable

import structlog
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text

from api.core.db import get_engine
from api.core.redis import get_redis

logger = structlog.get_logger(__name__)

router = APIRouter()

_CHECK_TIMEOUT_SECONDS = 2.0


async def ping_postgres() -> None:
    async with get_engine().connect() as connection:
        await connection.execute(text("SELECT 1"))


async def ping_redis() -> None:
    await get_redis().ping()


async def _is_up(name: str, ping: Callable[[], Awaitable[None]]) -> bool:
    try:
        await asyncio.wait_for(ping(), _CHECK_TIMEOUT_SECONDS)
    except Exception as exc:
        logger.warning("dependency_down", dependency=name, error_type=type(exc).__name__)
        return False
    return True


@router.get("/healthz", include_in_schema=False)
async def healthz() -> dict[str, str]:
    """Liveness: the process is up. Does not touch its dependencies."""
    return {"status": "ok"}


@router.get("/readyz", include_in_schema=False)
async def readyz() -> JSONResponse:
    """Readiness: Postgres and Redis both answer."""
    postgres, redis = await asyncio.gather(
        _is_up("postgres", ping_postgres), _is_up("redis", ping_redis)
    )
    ready = postgres and redis
    return JSONResponse(
        {
            "status": "ok" if ready else "unavailable",
            "checks": {
                "postgres": "ok" if postgres else "down",
                "redis": "ok" if redis else "down",
            },
        },
        status_code=200 if ready else 503,
    )
