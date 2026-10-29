"""Check the object store end to end, as clients and the worker use it (NFR-09).

    docker compose exec -e S3_PUBLIC_ENDPOINT_URL=http://minio:9000 api \\
        python -m api.scripts.storage_check

Uploads through a presigned URL, reads back through a signed one, and deletes
what it wrote. This is what proves the store accepts the signatures: the test
suite runs on moto, which does not check them. Run it where the public
endpoint is reachable; inside the api container that is MinIO's own name, as
above. Exits non-zero on the first step that fails.
"""

import asyncio
import urllib.request
from uuid import uuid4

from api.core.storage import Bucket, get_storage

_PAYLOAD = b"storage-check " * 64


def _check(ok: bool, step: str) -> None:
    if not ok:
        raise SystemExit(f"{step}: failed")
    print(f"{step}: ok")


def _send(request: urllib.request.Request) -> bytes:
    with urllib.request.urlopen(request, timeout=10) as response:  # noqa: S310
        body: bytes = response.read()
        return body


async def main() -> None:
    storage = get_storage()
    prefix = f"storage-check/{uuid4()}/"
    key = f"{prefix}object.bin"
    try:
        upload = await storage.presigned_put(
            Bucket.RAW, key, content_type="application/octet-stream"
        )
        put = urllib.request.Request(  # noqa: S310
            upload.url, data=_PAYLOAD, method=upload.method, headers=upload.headers
        )
        await asyncio.to_thread(_send, put)
        _check(True, "presigned upload")

        read = await asyncio.to_thread(
            _send,
            urllib.request.Request(await storage.signed_get(Bucket.RAW, key)),  # noqa: S310
        )
        _check(read == _PAYLOAD, "signed read")
        _check(await storage.get_object(Bucket.RAW, key) == _PAYLOAD, "worker read")
    finally:
        deleted = await storage.delete_prefix(Bucket.RAW, prefix)
    _check(deleted == 1, "delete by prefix")


if __name__ == "__main__":
    asyncio.run(main())
