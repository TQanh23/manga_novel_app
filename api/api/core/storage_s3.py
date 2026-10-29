"""`Storage` on S3 or anything that speaks its API, MinIO included (NFR-09).

The only module that imports the AWS SDK.
"""

import asyncio
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import boto3
import structlog
from botocore.config import Config

from api.core.config import Settings
from api.core.storage import Bucket, PresignedUpload

if TYPE_CHECKING:
    from types_boto3_s3.client import S3Client
    from types_boto3_s3.type_defs import ObjectIdentifierTypeDef

logger = structlog.get_logger(__name__)

# The most keys one DeleteObjects request takes.
_DELETE_BATCH = 1000


class S3Storage:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._buckets = {Bucket.RAW: settings.s3_bucket_raw, Bucket.TILES: settings.s3_bucket_tiles}
        # Talks to the store.
        self._client = self._make_client(settings.s3_endpoint_url)
        # Never connects: signing is local, but it must sign for the host clients use.
        self._signer = self._make_client(settings.s3_public_endpoint_url)

    def _make_client(self, endpoint_url: str) -> "S3Client":
        return boto3.session.Session().client(
            "s3",
            endpoint_url=endpoint_url,
            region_name=self._settings.s3_region,
            aws_access_key_id=self._settings.s3_access_key,
            aws_secret_access_key=self._settings.s3_secret_key.get_secret_value(),
            # MinIO serves buckets by path, not by subdomain.
            config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
        )

    async def presigned_put(
        self, bucket: Bucket, key: str, *, content_type: str
    ) -> PresignedUpload:
        ttl = self._settings.upload_url_ttl_seconds
        url = self._signer.generate_presigned_url(
            "put_object",
            Params={"Bucket": self._buckets[bucket], "Key": key, "ContentType": content_type},
            ExpiresIn=ttl,
            HttpMethod="PUT",
        )
        return PresignedUpload(
            url=url,
            method="PUT",
            headers={"Content-Type": content_type},
            expires_at=datetime.now(UTC) + timedelta(seconds=ttl),
        )

    async def signed_get(self, bucket: Bucket, key: str) -> str:
        return self._signer.generate_presigned_url(
            "get_object",
            Params={"Bucket": self._buckets[bucket], "Key": key},
            ExpiresIn=self._settings.signed_url_ttl_seconds,
        )

    async def put_object(self, bucket: Bucket, key: str, data: bytes, *, content_type: str) -> None:
        await asyncio.to_thread(
            self._client.put_object,
            Bucket=self._buckets[bucket],
            Key=key,
            Body=data,
            ContentType=content_type,
        )

    async def get_object(self, bucket: Bucket, key: str) -> bytes:
        def read() -> bytes:
            response = self._client.get_object(Bucket=self._buckets[bucket], Key=key)
            return response["Body"].read()

        return await asyncio.to_thread(read)

    async def delete_prefix(self, bucket: Bucket, prefix: str) -> int:
        if not prefix:
            raise ValueError("delete_prefix needs a prefix; an empty one would empty the bucket")
        name = self._buckets[bucket]

        def delete() -> int:
            deleted = 0
            pages = self._client.get_paginator("list_objects_v2").paginate(
                Bucket=name, Prefix=prefix, PaginationConfig={"PageSize": _DELETE_BATCH}
            )
            for page in pages:
                keys: list[ObjectIdentifierTypeDef] = [
                    {"Key": item["Key"]} for item in page.get("Contents", [])
                ]
                if not keys:
                    continue
                response = self._client.delete_objects(
                    Bucket=name, Delete={"Objects": keys, "Quiet": True}
                )
                if response.get("Errors"):
                    raise RuntimeError(
                        f"could not delete {len(response['Errors'])} objects in {name}"
                    )
                deleted += len(keys)
            return deleted

        deleted = await asyncio.to_thread(delete)
        # The prefix names ids only, never content.
        logger.info("storage_prefix_deleted", bucket=name, prefix=prefix, count=deleted)
        return deleted
