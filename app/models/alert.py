from datetime import datetime
from enum import Enum

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.timestamps import format_utc


class AlertLevel(str, Enum):
    HIGH = "high"
    ELEVATED = "elevated"
    RAPID_RISE = "rapid_rise"


class AlertStatus(str, Enum):
    ACTIVE = "active"
    ACKNOWLEDGED = "acknowledged"
    ALL_CLEAR = "all_clear"


class Alert(Base):
    __tablename__ = "air_alerts"
    __table_args__ = (
        Index(
            "uq_open_alert_home_room_metric_level",
            "home_id",
            "room_id",
            "metric_code",
            "level",
            unique=True,
            postgresql_where=text("status IN ('active', 'acknowledged')"),
            sqlite_where=text("status IN ('active', 'acknowledged')"),
        ),
        Index("ix_alerts_home_created_at", "home_id", "created_at"),
        CheckConstraint(
            "level IN ('high', 'elevated', 'rapid_rise')",
            name="ck_alerts_level",
        ),
        CheckConstraint(
            "status IN ('active', 'acknowledged', 'all_clear')",
            name="ck_alerts_status",
        ),
        CheckConstraint(
            "(status = 'active' AND acknowledged_at IS NULL AND "
            "acknowledged_by IS NULL AND all_clear_at IS NULL) OR "
            "(status = 'acknowledged' AND acknowledged_at IS NOT NULL AND "
            "acknowledged_by IS NOT NULL AND all_clear_at IS NULL) OR "
            "(status = 'all_clear' AND all_clear_at IS NOT NULL AND "
            "((acknowledged_at IS NULL AND acknowledged_by IS NULL) OR "
            "(acknowledged_at IS NOT NULL AND acknowledged_by IS NOT NULL)))",
            name="ck_alerts_transition_metadata",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    home_id: Mapped[str] = mapped_column(ForeignKey("homes.id"), nullable=False)
    room_id: Mapped[str] = mapped_column(ForeignKey("rooms.id"), nullable=False)
    metric_code: Mapped[str] = mapped_column(ForeignKey("metrics.code"), nullable=False)
    level: Mapped[str] = mapped_column(String(24), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="active")
    trigger_value: Mapped[float] = mapped_column(Float, nullable=False)
    threshold_value: Mapped[float] = mapped_column(Float, nullable=False)
    latest_value: Mapped[float] = mapped_column(Float, nullable=False)
    threshold_unit: Mapped[str] = mapped_column(String(24), nullable=False)
    clear_duration_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    below_threshold_since: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    acknowledged_by: Mapped[str | None] = mapped_column(String(120))
    all_clear_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    detail: Mapped[str] = mapped_column(Text, nullable=False)

    def to_dict(self, room_name: str | None = None, metric_name: str | None = None) -> dict:
        return {
            "id": self.id,
            "home_id": self.home_id,
            "room_id": self.room_id,
            "room": room_name,
            "metric": self.metric_code,
            "metric_name": metric_name,
            "level": self.level,
            "status": self.status,
            "trigger_value": self.trigger_value,
            "threshold_value": self.threshold_value,
            "latest_value": self.latest_value,
            "threshold_unit": self.threshold_unit,
            "clear_duration_seconds": self.clear_duration_seconds,
            "created_at": format_utc(self.created_at),
            "acknowledged_at": format_utc(self.acknowledged_at)
            if self.acknowledged_at
            else None,
            "acknowledged_by": self.acknowledged_by,
            "all_clear_at": format_utc(self.all_clear_at) if self.all_clear_at else None,
            "detail": self.detail,
        }