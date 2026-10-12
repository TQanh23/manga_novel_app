from enum import StrEnum

from sqlalchemy import Boolean, CheckConstraint, Integer, Text, UniqueConstraint, true
from sqlalchemy.orm import Mapped, mapped_column

from api.core.models import Base, TimestampMixin, UUIDPrimaryKeyMixin, one_of


class PresetKind(StrEnum):
    WUF_PERIOD = "wuf_period"
    REVENUE_SHARE = "revenue_share"


class ConfigPreset(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One value an author or admin may pick for a work (FR-AD-04).

    Works reference a preset instead of holding a free-form number, and each
    unlock snapshots the preset in force, so changing the list never rewrites
    past revenue. A preset is retired by clearing `active`, never deleted.
    """

    __tablename__ = "config_presets"
    __table_args__ = (
        UniqueConstraint("kind", "value"),
        CheckConstraint(one_of("kind", PresetKind), name="kind"),
        CheckConstraint("value > 0", name="value_positive"),
        CheckConstraint(
            f"kind <> '{PresetKind.REVENUE_SHARE}' OR value <= 100", name="revenue_share_percent"
        ),
        {"schema": "core"},
    )

    kind: Mapped[str] = mapped_column(Text)
    # wuf_period: seconds a reader waits. revenue_share: the author's percent.
    value: Mapped[int] = mapped_column(Integer)
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=true())
