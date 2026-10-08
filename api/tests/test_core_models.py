import time
from datetime import UTC, datetime

from sqlalchemy import ColumnDefault, DateTime
from sqlalchemy.orm import DeclarativeBase

from api.core.ids import uuid7
from api.core.models import TimestampMixin, UUIDPrimaryKeyMixin


def test_uuid7_is_version_7_and_carries_the_current_time() -> None:
    value = uuid7()

    timestamp_ms = value.int >> 80
    assert value.version == 7
    assert abs(timestamp_ms / 1000 - datetime.now(UTC).timestamp()) < 5


def test_uuid7_sorts_by_creation_time() -> None:
    earlier = uuid7()
    time.sleep(0.002)
    later = uuid7()

    assert earlier < later


def test_mixins_give_a_model_a_uuid7_key_and_timezone_aware_timestamps() -> None:
    class ScratchBase(DeclarativeBase):
        pass

    class Thing(UUIDPrimaryKeyMixin, TimestampMixin, ScratchBase):
        __tablename__ = "thing"

    columns = Thing.__table__.columns
    id_default = columns["id"].default

    assert columns["id"].primary_key
    assert isinstance(id_default, ColumnDefault)
    assert id_default.arg(None).version == 7
    for name in ("created_at", "updated_at"):
        column_type = columns[name].type
        assert isinstance(column_type, DateTime)
        assert column_type.timezone
        assert columns[name].server_default is not None
        assert not columns[name].nullable
    assert columns["updated_at"].onupdate is not None
