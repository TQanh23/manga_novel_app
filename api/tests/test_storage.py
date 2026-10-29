"""The Storage interface and its S3 implementation (NFR-09, NFR-05)."""

from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qs, urlsplit

import pytest

from api.core.config import get_settings
from api.core.storage import Bucket, Storage, get_storage
from api.core.storage_s3 import S3Storage
from api.testing import PUBLIC_STORAGE_URL


def _query(url: str) -> dict[str, str]:
    return {key: values[0] for key, values in parse_qs(urlsplit(url).query).items()}


async def test_nfr05_signed_read_urls_expire_after_five_minutes(storage: Storage) -> None:
    url = await storage.signed_get(Bucket.TILES, "works/w1/page-1.webp")

    assert _query(url)["X-Amz-Expires"] == "300"


async def test_signed_read_urls_point_where_clients_reach_the_store(storage: Storage) -> None:
    url = urlsplit(await storage.signed_get(Bucket.TILES, "works/w1/page-1.webp"))

    # Signed for the public host, by path, in the real bucket.
    assert f"{url.scheme}://{url.netloc}" == PUBLIC_STORAGE_URL
    assert url.path == "/test-tiles/works/w1/page-1.webp"


async def test_upload_urls_go_to_the_raw_bucket_and_sign_the_content_type(
    storage: Storage,
) -> None:
    before = datetime.now(UTC)
    upload = await storage.presigned_put(Bucket.RAW, "uploads/u1/1.png", content_type="image/png")

    url = urlsplit(upload.url)
    query = _query(upload.url)
    assert f"{url.scheme}://{url.netloc}" == PUBLIC_STORAGE_URL
    assert url.path == "/test-raw/uploads/u1/1.png"
    assert upload.method == "PUT"
    assert upload.headers == {"Content-Type": "image/png"}
    # A client that sends another type breaks the signature.
    assert "content-type" in query["X-Amz-SignedHeaders"].split(";")
    ttl = get_settings().upload_url_ttl_seconds
    assert query["X-Amz-Expires"] == str(ttl)
    assert before + timedelta(seconds=ttl) <= upload.expires_at
    assert upload.expires_at <= datetime.now(UTC) + timedelta(seconds=ttl)


async def test_an_object_reads_back_as_written(storage: Storage) -> None:
    data = bytes(range(256)) * 64

    await storage.put_object(Bucket.TILES, "works/w1/t.webp", data, content_type="image/webp")

    assert await storage.get_object(Bucket.TILES, "works/w1/t.webp") == data


async def test_deleting_a_prefix_removes_everything_under_it_and_nothing_else(
    storage: Storage,
) -> None:
    # More than one DeleteObjects request holds.
    keys = [f"works/w1/{index:04}.webp" for index in range(1001)]
    for key in keys:
        await storage.put_object(Bucket.TILES, key, b"x", content_type="image/webp")
    await storage.put_object(Bucket.TILES, "works/w10/0.webp", b"y", content_type="image/webp")
    await storage.put_object(Bucket.RAW, "works/w1/0.png", b"z", content_type="image/png")

    assert await storage.delete_prefix(Bucket.TILES, "works/w1/") == len(keys)

    assert await storage.delete_prefix(Bucket.TILES, "works/w1/") == 0
    # A neighbouring prefix and the other bucket are untouched.
    assert await storage.get_object(Bucket.TILES, "works/w10/0.webp") == b"y"
    assert await storage.get_object(Bucket.RAW, "works/w1/0.png") == b"z"


async def test_an_empty_prefix_is_refused(storage: Storage) -> None:
    await storage.put_object(Bucket.TILES, "keep.webp", b"x", content_type="image/webp")

    with pytest.raises(ValueError, match="empty"):
        await storage.delete_prefix(Bucket.TILES, "")

    assert await storage.get_object(Bucket.TILES, "keep.webp") == b"x"


def test_the_backend_comes_from_config() -> None:
    get_storage.cache_clear()
    try:
        assert get_settings().storage_backend == "s3"
        assert isinstance(get_storage(), S3Storage)
    finally:
        get_storage.cache_clear()
