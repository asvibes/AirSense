from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.user import HomeInvitation, HomeMembership, User
from app.services.audit import record_event


def accept_invitation_for_user(
    db: Session, *, user: User, token_hash: str
) -> tuple[dict | None, str | None, int]:
    """Validate and atomically consume an invitation for the authenticated user."""
    invitation = db.scalar(
        select(HomeInvitation).where(HomeInvitation.token_hash == token_hash)
    )
    if invitation is None or invitation.accepted_at is not None:
        db.rollback()
        return None, "This invitation is invalid or has already been used.", 404

    expires_at = invitation.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    now = datetime.now(timezone.utc)
    if expires_at <= now:
        db.rollback()
        return None, "This invitation has expired.", 410

    if user.email != invitation.email:
        db.rollback()
        return None, "Sign in with the email address this invitation was sent to.", 403

    if user.email_verified_at is None:
        db.rollback()
        return None, "Verify your email before accepting this invitation.", 403

    if db.get(HomeMembership, (invitation.home_id, user.id)) is not None:
        db.rollback()
        return None, "You are already a member of this home.", 409

    # The conditional update is the single-use claim. Unlike a read followed by
    # a write, it also protects concurrent acceptance on databases without row
    # locking support (including SQLite).
    claim = db.execute(
        update(HomeInvitation)
        .where(
            HomeInvitation.id == invitation.id,
            HomeInvitation.accepted_at.is_(None),
            HomeInvitation.expires_at > now,
        )
        .values(accepted_at=now)
        .execution_options(synchronize_session=False)
    )
    if claim.rowcount != 1:
        db.rollback()
        latest = db.scalar(
            select(HomeInvitation).where(HomeInvitation.id == invitation.id)
        )
        if latest is not None and latest.accepted_at is None:
            latest_expiry = latest.expires_at
            if latest_expiry.tzinfo is None:
                latest_expiry = latest_expiry.replace(tzinfo=timezone.utc)
            if latest_expiry <= datetime.now(timezone.utc):
                db.rollback()
                return None, "This invitation has expired.", 410
        return None, "This invitation is invalid or has already been used.", 404

    membership = HomeMembership(
        home_id=invitation.home_id,
        user_id=user.id,
        role=invitation.role,
    )
    db.add(membership)
    record_event(
        db,
        home_id=invitation.home_id,
        actor_user_id=user.id,
        event_type="member.joined",
        entity_type="user",
        entity_id=user.id,
        details={"role": invitation.role},
    )
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return None, "You are already a member of this home.", 409

    return {"home_id": invitation.home_id, "role": invitation.role}, None, 200


def valid_invitation_hash(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )
