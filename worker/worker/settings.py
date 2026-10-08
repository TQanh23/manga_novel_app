"""Settings arq runs the worker with. Start it with `python -m worker`."""

from typing import Any, ClassVar

import structlog
from arq.connections import RedisSettings
from arq.worker import Function

import worker.jobs  # noqa: F401 - registers the jobs
from api.core.config import get_settings
from api.core.db import get_engine
from api.core.queue import queue_name
from worker.runtime import MAX_TRIES, registered_functions

logger = structlog.get_logger(__name__)


async def startup(ctx: dict[str, Any]) -> None:
    logger.info(
        "worker_started",
        queue=queue_name(),
        jobs=sorted(function.name for function in registered_functions()),
    )


async def shutdown(ctx: dict[str, Any]) -> None:
    await get_engine().dispose()


class WorkerSettings:
    """The default queue. AI work gets its own queue and worker in Phase 4."""

    functions: ClassVar[list[Function]] = registered_functions()
    redis_settings = RedisSettings.from_dsn(get_settings().redis_url)
    queue_name = queue_name()
    max_tries = MAX_TRIES
    # State lives in core.jobs; nothing a job returns is kept in Redis.
    keep_result = 0
    # Also how often the key Compose's healthcheck looks for is refreshed.
    health_check_interval = 10
    on_startup = startup
    on_shutdown = shutdown
