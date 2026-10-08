from functools import lru_cache

from redis.asyncio import Redis

from api.core.config import get_settings


@lru_cache
def get_redis() -> Redis:
    client: Redis = Redis.from_url(get_settings().redis_url, decode_responses=True)
    return client


def redis_key(*parts: str) -> str:
    """Build a namespaced key. Every key the app writes goes through here."""
    return get_settings().redis_key_prefix + ":".join(parts)
