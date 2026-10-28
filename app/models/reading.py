from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Reading(Base):
    __tablename__ = "air_readings"
    __table_args__ = (
        UniqueConstraint(
            "home_id",
            "room_id",
            "metric_code",
            "measured_at",
            name="uq_readings_home_room_metric_time",
        ),
        Index(
            "ix_readings_home_room_metric_time",
            "home_id",
            "room_id",
            "metric_code",
            "measured_at",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    home_id: Mapped[str] = mapped_column(ForeignKey("homes.id"), nullable=False)
    room_id: Mapped[str] = mapped_column(ForeignKey("rooms.id"), nullable=False)
    sensor_id: Mapped[str | None] = mapped_column(
        ForeignKey("sensors.id", name="fk_air_readings_sensor_id_sensors")
    )
    metric_code: Mapped[str] = mapped_column(
        String(32), ForeignKey("metrics.code"), nullable=False
    )
    value: Mapped[float] = mapped_column(Float, nullable=False)
    source: Mapped[str] = mapped_column(String(24), nullable=False)
    measured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)