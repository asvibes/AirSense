from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Home(Base):
    __tablename__ = "homes"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    rooms: Mapped[list["Room"]] = relationship(back_populates="home")
    memberships: Mapped[list["HomeMembership"]] = relationship(
        back_populates="home", cascade="all, delete-orphan"
    )