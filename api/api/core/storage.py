"""Object storage behind one interface (NFR-09).

Images never pass through the API: clients upload with a presigned URL and
read with a signed one that expires after five minutes (NFR-05). Only the
worker moves object bytes itself. The vendor SDK is imported by the
implementation alone (`storage_s3.py`), never here or by callers.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from functools import lru_cache
from typing import Annotated, Protocol

from fastapi import Depends

from api.core.config import get_settings


class Bucket(StrEnum):
    """Where an object lives, by role. Settings map each to a real bucket name."""

    # What authors upload, as they uploaded it.
    RAW = "raw"
    # What the worker made from it, which readers see.
    TILES = "tiles"


@dataclass(frozen=True)
class PresignedUpload:
    """How a client uploads one object straight to the store."""

    url: str
    method: str
    # Headers the client must send as they are: they are part of the signature.
    headers: dict[str, str]
    expires_at: datetime


class Storage(Protocol):
    async def presigned_put(
        self, bucket: Bucket, key: str, *, content_type: str
    ) -> PresignedUpload:
        """A URL the client uploads `key` to, with `content_type` and nothing else."""
        ...

    async def signed_get(self, bucket: Bucket, key: str) -> str:
        """A URL the client reads `key` from, for `signed_url_ttl_seconds`."""
        ...

    async def put_object(
        self, bucket: Bucket, key: str, data: bytes, *, content_type: str
    ) -> None: ...

    async def get_object(self, bucket: Bucket, key: str) -> bytes: ...

    async def delete_prefix(self, bucket: Bucket, prefix: str) -> int:
        """Delete every object under `prefix` and return how many there were.

        An empty prefix is refused: it would empty the bucket.
        """
        ...


@lru_cache
def get_storage() -> Storage:
    settings = get_settings()
    match settings.storage_backend:
        case "s3":
            # Imported here: the implementation imports this module for `Bucket`.
            from api.core.storage_s3 import S3Storage

            return S3Storage(settings)


StorageDep = Annotated[Storage, Depends(get_storage)]
