import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from flask import Blueprint, jsonify, render_template, request
from sqlalchemy import select

from app.db import get_session
from app.models.home import Home
from app.models.user import HomeInvitation, HomeMembership, User
from app.schemas.auth import AuthInputError, validate_email
from app.security.sessions import current_user, list_user_homes, require_home_role, require_user
from app.services.audit import record_event


homes = Blueprint("homes", __name__)


@homes.get("/join")
@require_user(api=False)
def invitation_page():
    return render_template(
        "auth/join.html",
        token=request.args.get("token", ""),
        csrf_token=_csrf_token(),
    )


@homes.get("/api/homes")
@require_user()
def list_homes():
    return jsonify(homes=list_user_homes(current_user().id))


@homes.post("/api/homes")
@require_user()
def create_home():
    payload = request.get_json(silent=True) or {}
    name = payload.get("name")
    if not isinstance(name, str) or not name.strip() or len(name.strip()) > 120:
        return jsonify(error="name must contain 1 to 120 characters."), 400
    user = current_user()
    home = Home(id=str(uuid.uuid4()), name=name.strip())
    db = get_session()
    db.add_all(
        [home, HomeMembership(home_id=home.id, user_id=user.id, role="owner")]
    )
    record_event(
        db,
        home_id=home.id,
        actor_user_id=user.id,
        event_type="home.created",
        entity_type="home",
        entity_id=home.id,
    )
    db.commit()
    return jsonify(home={"id": home.id, "name": home.name, "role": "owner"}), 201


@homes.post("/api/active-home")
@require_user()
def choose_home():
    payload = request.get_json(silent=True) or {}
    home_id = payload.get("home_id")
    if not isinstance(home_id, str):
        return jsonify(error="home_id is required."), 400
    require_home_role(home_id, "owner", "member")
    from flask import session

    session["home_id"] = home_id
    return jsonify(home_id=home_id)


@homes.get("/api/homes/<home_id>/members")
@require_user()
def list_members(home_id: str):
    require_home_role(home_id, "owner", "member")
    db = get_session()
    rows = db.execute(
        select(User.id, User.email, User.display_name, HomeMembership.role, HomeMembership.joined_at)
        .join(HomeMembership, HomeMembership.user_id == User.id)
        .where(HomeMembership.home_id == home_id)
        .order_by(HomeMembership.joined_at)
    ).all()
    return jsonify(
        members=[
            {
                "user_id": row.id,
                "email": row.email,
                "display_name": row.display_name,
                "role": row.role,
                "joined_at": row.joined_at.isoformat(),
            }
            for row in rows
        ]
    )


@homes.post("/api/homes/<home_id>/invitations")
@require_user()
def invite_member(home_id: str):
    require_home_role(home_id, "owner")
    payload = request.get_json(silent=True) or {}
    try:
        email = validate_email(payload.get("email"))
    except AuthInputError as error:
        return jsonify(error=str(error)), 400
    db = get_session()
    if db.scalar(
        select(HomeMembership.user_id)
        .join(User, User.id == HomeMembership.user_id)
        .where(HomeMembership.home_id == home_id, User.email == email)
    ):
        return jsonify(error="This person is already a member of the home."), 409
    now = datetime.now(timezone.utc)
    invitation_token = secrets.token_urlsafe(32)
    invitation = HomeInvitation(
        id=str(uuid.uuid4()),
        home_id=home_id,
        email=email,
        role="member",
        token_hash=hashlib.sha256(invitation_token.encode()).hexdigest(),
        created_by=current_user().id,
        created_at=now,
        expires_at=now + timedelta(days=7),
    )
    db.add(invitation)
    record_event(
        db,
        home_id=home_id,
        actor_user_id=current_user().id,
        event_type="member.invited",
        entity_type="invitation",
        entity_id=invitation.id,
        details={"email": email, "expires_at": invitation.expires_at.isoformat()},
    )
    db.commit()
    return jsonify(
        invitation={
            "id": invitation.id,
            "email": email,
            "role": invitation.role,
            "expires_at": invitation.expires_at.isoformat(),
            "token": invitation_token,
            "delivery": "Copy this one-time code to the invited person. Email delivery is not configured.",
        }
    ), 201


@homes.post("/api/invitations/accept")
@require_user()
def accept_invitation():
    payload = request.get_json(silent=True) or {}
    token = payload.get("token")
    if not isinstance(token, str) or not token or len(token) > 200:
        return jsonify(error="A valid invitation token is required."), 400
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    db = get_session()
    invitation = db.scalar(
        select(HomeInvitation)
        .where(HomeInvitation.token_hash == token_hash)
        .with_for_update()
    )
    if invitation is None or invitation.accepted_at is not None:
        return jsonify(error="This invitation is invalid or has already been used."), 404
    expires = invitation.expires_at
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    if expires <= datetime.now(timezone.utc):
        return jsonify(error="This invitation has expired."), 410
    user = current_user()
    if user.email != invitation.email:
        return jsonify(error="Sign in with the email address this invitation was sent to."), 403
    if db.get(HomeMembership, (invitation.home_id, user.id)) is not None:
        return jsonify(error="You are already a member of this home."), 409
    db.add(
        HomeMembership(
            home_id=invitation.home_id, user_id=user.id, role=invitation.role
        )
    )
    invitation.accepted_at = datetime.now(timezone.utc)
    record_event(
        db,
        home_id=invitation.home_id,
        actor_user_id=user.id,
        event_type="member.joined",
        entity_type="user",
        entity_id=user.id,
    )
    db.commit()
    return jsonify(home_id=invitation.home_id, role=invitation.role)


@homes.delete("/api/homes/<home_id>/members/<user_id>")
@require_user()
def remove_member(home_id: str, user_id: str):
    require_home_role(home_id, "owner")
    if user_id == current_user().id:
        return jsonify(error="The home owner cannot remove themselves."), 409
    db = get_session()
    membership = db.get(HomeMembership, (home_id, user_id))
    if membership is None:
        return jsonify(error="Member not found."), 404
    if membership.role == "owner":
        return jsonify(error="An owner cannot be removed from the home."), 409
    db.delete(membership)
    record_event(
        db,
        home_id=home_id,
        actor_user_id=current_user().id,
        event_type="member.removed",
        entity_type="user",
        entity_id=user_id,
    )
    db.commit()
    return jsonify(status="removed")


def _csrf_token() -> str:
    from app.security.sessions import csrf_token

    return csrf_token()