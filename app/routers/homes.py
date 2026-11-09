import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from flask import Blueprint, current_app, jsonify, redirect, render_template, request, session, url_for
from sqlalchemy import select

from app.db import get_session
from app.json_request import require_json_object
from app.models.home import Home
from app.models.user import HomeInvitation, HomeMembership, User
from app.schemas.auth import AuthInputError, validate_email
from app.security.sessions import current_user, list_user_homes, require_home_role, require_user
from app.security.rate_limit import allow_persistent
from app.services.audit import record_event
from app.services.email import EmailDeliveryError, send_invitation_email
from app.services.invitations import accept_invitation_for_user, valid_invitation_hash
from app.timestamps import format_utc


homes = Blueprint("homes", __name__)


@homes.get("/join")
def invitation_page():
    token = request.args.get("token")
    if isinstance(token, str) and token and len(token) <= 200:
        session["pending_invitation_hash"] = hashlib.sha256(token.encode()).hexdigest()

    pending_hash = session.get("pending_invitation_hash")
    if not valid_invitation_hash(pending_hash):
        pending_hash = None
        session.pop("pending_invitation_hash", None)

    user = current_user()
    error_messages = {
        "wrong-account": "This invitation was sent to a different email address. Sign out and sign in with the invited account.",
        "expired": "This invitation has expired.",
        "invalid": "This invitation is invalid or has already been used.",
        "already-member": "You are already a member of this home.",
    }
    error = error_messages.get(request.args.get("error"))
    if pending_hash is None and (
        user is None or not user.is_active or error is None
    ):
        return redirect(url_for("landing"))

    if user is None or not user.is_active:
        return redirect(url_for("auth.login_page", next=url_for("homes.invitation_page")))

    return render_template(
        "auth/join.html",
        token="",
        auto_accept=bool(pending_hash and user is not None and not error),
        invitation_error=error,
        show_switch_account=bool(error == "wrong-account" and user is not None),
        csrf_token=_csrf_token(),
    )


@homes.get("/api/homes")
@require_user()
def list_homes():
    return jsonify(homes=list_user_homes(current_user().id))


@homes.post("/api/homes")
@require_user()
def create_home():
    payload = require_json_object()
    name = payload.get("name")
    if not isinstance(name, str) or not name.strip() or len(name.strip()) > 120:
        return jsonify(error="name must contain 1 to 120 characters."), 400
    user = current_user()
    home = Home(id=str(uuid.uuid4()), name=name.strip())
    db = get_session()
    db.add_all(
        [home, HomeMembership(home_id=home.id, user_id=user.id, role="owner")]
    )
    db.flush()
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
    payload = require_json_object()
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
                "joined_at": format_utc(row.joined_at),
            }
            for row in rows
        ]
    )


@homes.post("/api/homes/<home_id>/invitations")
@require_user()
def invite_member(home_id: str):
    require_home_role(home_id, "owner")
    if not allow_persistent(
        get_session(),
        f"invite:home:{home_id}:user:{current_user().id}",
        limit=20,
        window_seconds=900,
    ):
        return jsonify(error="Invitation rate limit exceeded."), 429
    payload = require_json_object()
    try:
        email = validate_email(payload.get("email"))
    except AuthInputError as error:
        return jsonify(error=str(error)), 400
    db = get_session()
    # Serialize invitations for this home so concurrent submissions cannot
    # both pass the active-invitation check on databases with row locking.
    home = db.scalar(
        select(Home).where(Home.id == home_id).with_for_update()
    )
    if db.scalar(
        select(HomeMembership.user_id)
        .join(User, User.id == HomeMembership.user_id)
        .where(HomeMembership.home_id == home_id, User.email == email)
    ):
        return jsonify(error="This person is already a member of the home."), 409
    now = datetime.now(timezone.utc)
    active_invitation_id = db.scalar(
        select(HomeInvitation.id)
        .where(
            HomeInvitation.home_id == home_id,
            HomeInvitation.email == email,
            HomeInvitation.accepted_at.is_(None),
            HomeInvitation.expires_at > now,
        )
        .limit(1)
    )
    if active_invitation_id is not None:
        db.rollback()
        return jsonify(
            error="An active invitation has already been sent to this address."
        ), 409

    invitation_token = secrets.token_urlsafe(32)
    invitation = HomeInvitation(
        id=str(uuid.uuid4()),
        home_id=home_id,
        email=email,
        role="member",
        token_hash=hashlib.sha256(invitation_token.encode()).hexdigest(),
        created_by=current_user().id,
        created_at=now,
        expires_at=now + timedelta(hours=24),
    )
    db.add(invitation)
    record_event(
        db,
        home_id=home_id,
        actor_user_id=current_user().id,
        event_type="member.invited",
        entity_type="invitation",
        entity_id=invitation.id,
        details={
            "email": email,
            "role": invitation.role,
            "expires_at": format_utc(invitation.expires_at),
        },
    )
    try:
        db.flush()
        base_url = current_app.config.get("PUBLIC_BASE_URL")
        if not base_url:
            if current_app.config.get("APP_ENV") == "production":
                raise EmailDeliveryError(
                    "PUBLIC_BASE_URL must be configured for invitation links."
                )
            base_url = request.host_url.rstrip("/")
        send_invitation_email(
            recipient=email,
            invitation_url=f"{base_url}{url_for('homes.invitation_page')}?token={invitation_token}",
            expires_at=invitation.expires_at,
            owner_name=current_user().display_name,
        )
        db.commit()
    except EmailDeliveryError as error:
        db.rollback()
        return jsonify(error=str(error)), 503
    return jsonify(
        invitation={
            "id": invitation.id,
            "email": email,
            "role": invitation.role,
            "expires_at": format_utc(invitation.expires_at),
            "token": invitation_token,
            "delivery": "Invitation email sent.",
        }
    ), 201


@homes.post("/api/invitations/accept")
@require_user()
def accept_invitation():
    payload = require_json_object()
    token = payload.get("token")
    if token is None:
        token_hash = session.get("pending_invitation_hash")
        if not valid_invitation_hash(token_hash):
            return jsonify(error="A valid invitation token is required."), 400
    elif isinstance(token, str) and token and len(token) <= 200:
        token_hash = hashlib.sha256(token.encode()).hexdigest()
    else:
        return jsonify(error="A valid invitation token is required."), 400

    result, error, status = accept_invitation_for_user(
        get_session(), user=current_user(), token_hash=token_hash
    )
    if result is None:
        if status != 403 and session.get("pending_invitation_hash") == token_hash:
            session.pop("pending_invitation_hash", None)
        return jsonify(error=error), status

    if session.get("pending_invitation_hash") == token_hash:
        session.pop("pending_invitation_hash", None)
    session["home_id"] = result["home_id"]
    return jsonify(**result)


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
        details={"role": membership.role},
    )
    db.commit()
    return jsonify(status="removed")


def _csrf_token() -> str:
    from app.security.sessions import csrf_token

    return csrf_token()
