import hashlib
import time
from collections.abc import Awaitable, Callable

import structlog
from fastapi import Request
from redis.exceptions import RedisError

from api.core.config import get_settings
from api.core.errors import AppError
from api.core.redis import get_redis, redis_key

logger = structlog.get_logger(__name__)


def hash_identity(value: str) -> str:
    """Stable stand-in for an email, so addresses are not stored in Redis keys."""
    return hashlib.sha256(value.strip().lower().encode()).hexdigest()[:32]


def client_ip(request: Request) -> str:
    # The socket peer. Behind a reverse proxy this must come from the proxy's
    # forwarded header instead; that is decided with the demo host (D7).
    return request.client.host if request.client else "unknown"


async def enforce_rate_limit(scope: str, identity: str, *, limit: int) -> None:
    """Count one hit in the current fixed window; raise 429 once over the limit."""
    window = get_settings().rate_limit_window_seconds
    now = int(time.time())
    key = redis_key("rate", scope, identity, str(now // window))

    try:
        async with get_redis().pipeline(transaction=True) as pipeline:
            pipeline.incr(key)
            pipeline.expire(key, window)
            count, _ = await pipeline.execute()
    except RedisError as exc:
        # Redis being down should not take login down with it.
        logger.warning("rate_limit_unavailable", scope=scope, error_type=type(exc).__name__)
        return

    if count > limit:
        raise AppError(
            "rate_limited",
            "Too many requests. Try again shortly.",
            status_code=429,
            headers={"Retry-After": str(window - now % window)},
        )


def limit_by_ip(scope: str) -> Callable[[Request], Awaitable[None]]:
    """Route dependency: limit by client address."""

    async def dependency(request: Request) -> None:
        await enforce_rate_limit(
            f"{scope}:ip", client_ip(request), limit=get_settings().rate_limit_auth_per_ip
        )

    return dependency


async def limit_by_identity(scope: str, identity: str, *, limit: int | None = None) -> None:
    """Limit by the account being acted on (an email, a user id), whatever the address.

    Without `limit` this is the auth limit, which is deliberately tight.
    """
    await enforce_rate_limit(
        f"{scope}:id",
        hash_identity(identity),
        limit=get_settings().rate_limit_auth_per_identity if limit is None else limit,
    )
