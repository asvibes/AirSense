from sqlalchemy import ForeignKey, Index, String, UniqueConstraint, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Room(Base):
    __tablename__ = "rooms"
    __table_args__ = (
        UniqueConstraint("home_id", "name", name="uq_rooms_home_name"),
        Index(
            "uq_rooms_home_lower_name",
            "home_id",
            func.lower(text("name")),
            unique=True,
        ),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    home_id: Mapped[str] = mapped_column(ForeignKey("homes.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    home: Mapped["Home"] = relationship(back_populates="rooms")