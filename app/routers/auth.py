import uuid

from flask import Blueprint, current_app, jsonify, redirect, render_template, request, session, url_for
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from werkzeug.security import check_password_hash, generate_password_hash

from app.db import get_session
from app.models.home import Home
from app.models.user import HomeMembership, User
from app.schemas.auth import AuthInputError, validate_display_name, validate_email
from app.security.passwords import hash_password, validate_password, verify_password
from app.security.rate_limit import InMemoryRateLimiter
from app.security.sessions import current_user, csrf_token
from app.services.audit import record_event


auth = Blueprint("auth", __name__)
_DUMMY_PASSWORD_HASH = generate_password_hash("not-a-real-account-password", method="scrypt")


def _payload() -> dict:
    if request.is_json:
        body = request.get_json(silent=True)
        if not isinstance(body, dict):
            raise AuthInputError("Request body must be a JSON object.")
        return body
    return request.form.to_dict()


def _csrf(payload: dict) -> None:
    from app.security.sessions import verify_csrf

    verify_csrf()


def _rate_limit(action: str, limit: int = 10) -> bool:
    limiter: InMemoryRateLimiter = current_app.extensions["airsense_rate_limiter"]
    return limiter.allow(
        f"auth:{action}:{request.remote_addr or 'unknown'}",
        limit=limit,
        window_seconds=900,
    )


def _auth_error(message: str, status: int = 400):
    if request.is_json or request.path.startswith("/api/"):
        return jsonify(error=message), status
    template = (
        "auth/register.html"
        if request.path.endswith("/register")
        else "auth/login.html"
    )
    return render_template(template, csrf_token=csrf_token(), error=message), status


@auth.get("/login")
def login_page():
    if current_user():
        return redirect(url_for("alerts.alerts_page"))
    return render_template("auth/login.html", csrf_token=csrf_token(), error=None)


@auth.get("/register")
def register_page():
    if current_user():
        return redirect(url_for("alerts.alerts_page"))
    return render_template("auth/register.html", csrf_token=csrf_token(), error=None)


@auth.get("/api/me")
def me():
    user = current_user()
    if user is None or not user.is_active:
        return jsonify(error="Authentication is required."), 401
    from app.security.sessions import list_user_homes

    return jsonify(
        user={"id": user.id, "email": user.email, "display_name": user.display_name},
        csrf_token=csrf_token(),
        homes=list_user_homes(user.id),
    )


@auth.post("/api/auth/register")
@auth.post("/register")
def register():
    if not _rate_limit("register", 8):
        return _auth_error("Too many registration attempts. Try again later.", 429)
    try:
        payload = _payload()
        _csrf(payload)
        email = validate_email(payload.get("email"))
        name = validate_display_name(payload.get("display_name", payload.get("name")))
        password = payload.get("password")
        validate_password(password)
    except (AuthInputError, ValueError, TypeError) as error:
        return _auth_error(str(error))

    db = get_session()
    if db.scalar(select(User.id).where(User.email == email)):
        return _auth_error("Unable to create the account with those details.", 409)
    user = User(
        id=str(uuid.uuid4()),
        email=email,
        display_name=name,
        password_hash=hash_password(password),
    )
    home = Home(id=str(uuid.uuid4()), name=f"{name}'s home")
    db.add_all(
        [
            user,
            home,
            HomeMembership(home_id=home.id, user_id=user.id, role="owner"),
        ]
    )
    record_event(
        db,
        home_id=home.id,
        actor_user_id=user.id,
        event_type="account.registered",
        entity_type="home",
        entity_id=home.id,
    )
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return _auth_error("Unable to create the account with those details.", 409)
    session.clear()
    session["user_id"] = user.id
    session.permanent = True
    csrf_token()
    if request.is_json:
        return jsonify(user={"id": user.id, "email": user.email, "display_name": user.display_name}, home={"id": home.id, "name": home.name}), 201
    return redirect(url_for("alerts.alerts_page"))


@auth.post("/api/auth/login")
@auth.post("/login")
def login():
    if not _rate_limit("login", 10):
        return _auth_error("Too many sign-in attempts. Try again later.", 429)
    try:
        payload = _payload()
        _csrf(payload)
        email = validate_email(payload.get("email"))
        password = payload.get("password")
        if not isinstance(password, str) or len(password) > 256:
            raise AuthInputError("Email or password is incorrect.")
    except (AuthInputError, ValueError, TypeError):
        check_password_hash(_DUMMY_PASSWORD_HASH, "invalid")
        return _auth_error("Email or password is incorrect.", 401)

    user = get_session().scalar(select(User).where(User.email == email))
    if (
        user is None
        or not user.is_active
        or not verify_password(user.password_hash if user else _DUMMY_PASSWORD_HASH, password)
    ):
        return _auth_error("Email or password is incorrect.", 401)
    session.clear()
    session["user_id"] = user.id
    session.permanent = True
    csrf_token()
    if request.is_json:
        return jsonify(user={"id": user.id, "email": user.email, "display_name": user.display_name})
    next_url = request.args.get("next", "")
    if next_url.startswith("/") and not next_url.startswith("//"):
        return redirect(next_url)
    return redirect(url_for("alerts.alerts_page"))


@auth.post("/api/auth/logout")
@auth.post("/logout")
def logout():
    if current_user() is None:
        return jsonify(error="Authentication is required."), 401
    from app.security.sessions import verify_csrf

    verify_csrf()
    session.clear()
    if request.is_json or request.path.startswith("/api/"):
        return jsonify(status="signed_out")
    return redirect(url_for("auth.login_page"))