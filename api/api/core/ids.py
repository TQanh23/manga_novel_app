from uuid import UUID

from uuid_utils.compat import uuid7 as _uuid7


def uuid7() -> UUID:
    """Time-ordered UUID (RFC 9562 version 7), used for every primary key."""
    return _uuid7()
