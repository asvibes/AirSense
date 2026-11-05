from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Sensor(Base):
    __tablename__ = "sensors"
    __table_args__ = (
        Index("ix_sensors_home_room", "home_id", "room_id"),
        CheckConstraint(
            "status IN ('active', 'revoked')",
            name="ck_sensors_status",
        ),
        CheckConstraint(
            "reporting_interval_seconds BETWEEN 30 AND 86400",
            name="ck_sensors_reporting_interval",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    home_id: Mapped[str] = mapped_column(ForeignKey("homes.id"), nullable=False)
    room_id: Mapped[str] = mapped_column(ForeignKey("rooms.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    key_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="active", server_default="active"
    )
    reporting_interval_seconds: Mapped[int] = mapped_column(
        Integer, nullable=False, default=300, server_default="300"
    )
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    room: Mapped["Room"] = relationship()