from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class ThresholdPolicy(Base):
    __tablename__ = "threshold_policies"
    __table_args__ = (
        UniqueConstraint(
            "home_id",
            "room_id",
            "metric_code",
            name="uq_threshold_policy_scope",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    home_id: Mapped[str] = mapped_column(ForeignKey("homes.id"), nullable=False)
    room_id: Mapped[str] = mapped_column(ForeignKey("rooms.id"), nullable=False)
    metric_code: Mapped[str] = mapped_column(ForeignKey("metrics.code"), nullable=False)
    high_threshold: Mapped[float] = mapped_column(Float, nullable=False)
    elevated_threshold: Mapped[float] = mapped_column(Float, nullable=False)
    elevated_duration_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    rapid_rise_per_minute: Mapped[float] = mapped_column(Float, nullable=False)
    all_clear_duration_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    max_reading_gap_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    elevated_since: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
