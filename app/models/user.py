from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, func, true
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    email: Mapped[str] = mapped_column(String(254), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(120), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(256), nullable=False)
    session_version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=true()
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    memberships: Mapped[list["HomeMembership"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class HomeMembership(Base):
    __tablename__ = "home_memberships"

    home_id: Mapped[str] = mapped_column(
        ForeignKey("homes.id"), primary_key=True, index=True
    )
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id"), primary_key=True, index=True
    )
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    home: Mapped["Home"] = relationship(back_populates="memberships")
    user: Mapped["User"] = relationship(back_populates="memberships")


class HomeInvitation(Base):
    __tablename__ = "home_invitations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    home_id: Mapped[str] = mapped_column(ForeignKey("homes.id"), nullable=False)
    email: Mapped[str] = mapped_column(String(254), nullable=False)
    role: Mapped[str] = mapped_column(
        String(16), nullable=False, default="member", server_default="member"
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class EmailChallenge(Base):
    __tablename__ = "email_challenges"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    email: Mapped[str] = mapped_column(String(254), index=True, nullable=False)
    purpose: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    otp_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reset_token_hash: Mapped[str | None] = mapped_column(String(64), unique=True)
    reset_token_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reset_token_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class RateLimitBucket(Base):
    __tablename__ = "rate_limit_buckets"

    key: Mapped[str] = mapped_column(String(255), primary_key=True)
    window_started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")