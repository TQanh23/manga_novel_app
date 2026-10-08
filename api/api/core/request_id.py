import re

import structlog

from api.core.ids import uuid7

REQUEST_ID_HEADER = "X-Request-ID"

# A caller-supplied id ends up in logs and response headers, so it is only kept
# when it is short and made of characters that are safe in both.
_VALID_REQUEST_ID = re.compile(r"[A-Za-z0-9._-]{1,64}")


def resolve_request_id(incoming: str | None) -> str:
    """Keep the caller's request id when it is well formed, otherwise mint one."""
    if incoming is not None and _VALID_REQUEST_ID.fullmatch(incoming):
        return incoming
    return str(uuid7())


def get_request_id() -> str | None:
    """Request id bound to the current request or job, if any."""
    value = structlog.contextvars.get_contextvars().get("request_id")
    return value if isinstance(value, str) else None
