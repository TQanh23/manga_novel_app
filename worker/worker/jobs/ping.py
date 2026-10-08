import structlog

from worker.runtime import JobContext, job

logger = structlog.get_logger(__name__)

KIND = "ping"


@job(KIND)
async def ping(context: JobContext) -> None:
    """Does nothing. Proves the API can reach the worker and back."""
    logger.info("pong", target_id=str(context.target_id))
