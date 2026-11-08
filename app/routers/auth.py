import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit

from flask import Blueprint, current_app, jsonify, redirect, render_template, request, session, url_for
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from werkzeug.security import check_password_hash, generate_password_hash

from app.db import get_session
from app.models.home import Home
from app.models.user import EmailChallenge, HomeMembership, User
from app.schemas.auth import AuthInputError, validate_display_name, validate_email
from app.security.passwords import hash_password, validate_password, verify_password
from app.security.rate_limit import (
    allow_persistent,
    is_persistent_rate_limited,
    record_persistent_failure,
)
from app.security.sessions import current_user, csrf_token
from app.services.audit import record_event
from app.services.email import EmailDeliveryError, send_otp_email


auth = Blueprint("auth", __name__)
_DUMMY_PASSWORD_HASH = generate_password_hash("not-a-real-account-password", method="scrypt")


def _record_user_auth_event(
    db,
    user_id: str,
    event_type: str,
    details: dict | None = None,
    *,
    actor_user_id: str | None = None,
) -> None:
    home_ids = db.scalars(
        select(HomeMembership.home_id)
        .where(HomeMembership.user_id == user_id)
        .order_by(HomeMembership.home_id)
    )
    for home_id in home_ids:
        record_event(
            db,
            home_id=home_id,
            actor_user_id=actor_user_id,
            event_type=event_type,
            entity_type="user",
            entity_id=user_id,
            details=details,
        )


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


def _client_ip() -> str:
    return request.remote_addr or "unknown"


def _ip_rate_limit(action: str, *, limit: int) -> bool:
    return allow_persistent(
        get_session(),
        f"auth:{action}:ip:{_client_ip()}",
        limit=limit,
        window_seconds=current_app.config["AUTH_RATE_LIMIT_WINDOW_SECONDS"],
    )


def _email_rate_limit(action: str, email: str | None, *, ip_limit: int, email_limit: int) -> bool:
    db = get_session()
    if not allow_persistent(
        db,
        f"auth:{action}:ip:{_client_ip()}",
        limit=ip_limit,
        window_seconds=current_app.config["AUTH_RATE_LIMIT_WINDOW_SECONDS"],
    ):
        return False
    if email:
        return allow_persistent(
            db,
            f"auth:{action}:email:{email}",
            limit=email_limit,
            window_seconds=current_app.config["AUTH_RATE_LIMIT_WINDOW_SECONDS"],
        )
    return True


def _login_failure_rate_limited(email: str) -> bool:
    db = get_session()
    window_seconds = current_app.config["AUTH_RATE_LIMIT_WINDOW_SECONDS"]
    if is_persistent_rate_limited(
        db,
        f"auth:login-failure:ip:{_client_ip()}",
        limit=10,
        window_seconds=window_seconds,
    ):
        return True
    return is_persistent_rate_limited(
        db,
        f"auth:login-failure:email:{email}",
        limit=10,
        window_seconds=window_seconds,
    )


def _record_login_failure(email: str) -> bool:
    db = get_session()
    window_seconds = current_app.config["AUTH_RATE_LIMIT_WINDOW_SECONDS"]
    ip_allowed = record_persistent_failure(
        db,
        f"auth:login-failure:ip:{_client_ip()}",
        limit=10,
        window_seconds=window_seconds,
    )
    email_allowed = record_persistent_failure(
        db,
        f"auth:login-failure:email:{email}",
        limit=10,
        window_seconds=window_seconds,
    )
    return ip_allowed and email_allowed


def _auth_error(message: str, status: int = 400):
    if request.is_json or request.path.startswith("/api/"):
        return jsonify(error=message), status
    template = "auth/login.html"
    if request.path.endswith("/register"):
        template = "auth/register.html"
    elif request.path.endswith("/verify-email"):
        template = "auth/verify_email.html"
    elif request.path.endswith("/forgot-password"):
        template = "auth/forgot_password.html"
    elif request.path.endswith("/reset-password"):
        template = "auth/reset_password.html"
    elif request.path.endswith("/verify-reset"):
        template = "auth/verify_reset.html"
    return render_template(
        template,
        csrf_token=csrf_token(),
        error=message,
        email=request.form.get("email", ""),
        token=request.form.get("token", ""),
        next_url=request.args.get("next", ""),
    ), status


def _challenge_hash(otp: str) -> str:
    secret = current_app.config["SECRET_KEY"]
    return hashlib.sha256(f"{secret}:{otp}".encode()).hexdigest()


def _reset_token_hash(token: str) -> str:
    secret = current_app.config["SECRET_KEY"]
    return hashlib.sha256(f"{secret}:reset:{token}".encode()).hexdigest()


def _new_challenge(db, *, user: User | None, email: str, purpose: str) -> tuple[EmailChallenge, str]:
    now = datetime.now(timezone.utc)
    latest = db.scalar(
        select(EmailChallenge)
        .where(
            EmailChallenge.email == email,
            EmailChallenge.purpose == purpose,
            EmailChallenge.consumed_at.is_(None),
        )
        .order_by(EmailChallenge.created_at.desc())
    )
    if latest and (now - _aware(latest.last_sent_at)).total_seconds() < current_app.config["OTP_RESEND_COOLDOWN_SECONDS"]:
        raise AuthInputError("Please wait before requesting another code.")
    otp = f"{secrets.randbelow(1_000_000):06d}"
    challenge = EmailChallenge(
        id=str(uuid.uuid4()),
        user_id=user.id if user else None,
        email=email,
        purpose=purpose,
        otp_hash=_challenge_hash(otp),
        created_at=now,
        expires_at=now + timedelta(seconds=current_app.config["OTP_EXPIRY_SECONDS"]),
        last_sent_at=now,
        attempts=0,
    )
    db.add(challenge)
    db.flush()
    return challenge, otp


def _aware(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


def _verify_challenge(db, *, email: str, purpose: str, otp: str) -> EmailChallenge:
    challenge = db.scalar(
        select(EmailChallenge)
        .where(
            EmailChallenge.email == email,
            EmailChallenge.purpose == purpose,
            EmailChallenge.consumed_at.is_(None),
        )
        .order_by(EmailChallenge.created_at.desc())
    )
    now = datetime.now(timezone.utc)
    if challenge is None or _aware(challenge.expires_at) <= now:
        raise AuthInputError("That code is invalid or has expired.")
    if challenge.attempts >= current_app.config["OTP_MAX_ATTEMPTS"]:
        raise AuthInputError("Too many incorrect attempts. Request a new code.")
    challenge.attempts += 1
    if not isinstance(otp, str) or not secrets.compare_digest(challenge.otp_hash, _challenge_hash(otp)):
        db.commit()
        raise AuthInputError("That code is invalid or has expired.")
    challenge.consumed_at = now
    db.flush()
    return challenge


@auth.get("/login")
def login_page():
    if current_user():
        return redirect(url_for("alerts.alerts_page"))
    return render_template(
        "auth/login.html",
        csrf_token=csrf_token(),
        error=None,
        next_url=request.args.get("next", ""),
    )


@auth.get("/verify-email")
def verify_email_page():
    return render_template(
        "auth/verify_email.html",
        csrf_token=csrf_token(),
        email=request.args.get("email", ""),
        next_url=request.args.get("next", ""),
        error=None,
    )


@auth.get("/forgot-password")
def forgot_password_page():
    return render_template("auth/forgot_password.html", csrf_token=csrf_token(), error=None)


@auth.get("/reset-password")
def reset_password_page():
    return render_template("auth/reset_password.html", csrf_token=csrf_token(), error=None, token=request.args.get("token", ""))


@auth.get("/register")
def register_page():
    if current_user():
        return redirect(url_for("alerts.alerts_page"))
    return render_template(
        "auth/register.html",
        csrf_token=csrf_token(),
        error=None,
        next_url=request.args.get("next", ""),
    )


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
    try:
        payload = _payload()
        _csrf(payload)
        email = validate_email(payload.get("email"))
        name = validate_display_name(payload.get("display_name", payload.get("name")))
        password = payload.get("password")
        validate_password(password)
    except (AuthInputError, ValueError, TypeError) as error:
        return _auth_error(str(error))

    if not _email_rate_limit("register", email, ip_limit=8, email_limit=3):
        return _auth_error("Too many registration attempts. Try again later.", 429)

    db = get_session()
    if db.scalar(select(User.id).where(User.email == email)):
        return _auth_error("Unable to create the account with those details.", 409)
    user = User(
        id=str(uuid.uuid4()),
        email=email,
        display_name=name,
        password_hash=hash_password(password),
        is_active=True,
        email_verified_at=(
            datetime.now(timezone.utc)
            if not current_app.config["EMAIL_VERIFICATION_REQUIRED"]
            else None
        ),
    )
    db.add(user)
    home = None
    if not current_app.config["EMAIL_VERIFICATION_REQUIRED"]:
        home = Home(id=str(uuid.uuid4()), name=f"{name}'s home")
        db.add_all(
            [
                home,
                HomeMembership(home_id=home.id, user_id=user.id, role="owner"),
            ]
        )
    db.flush()
    if home is not None:
        record_event(
            db,
            home_id=home.id,
            actor_user_id=user.id,
            event_type="account.registered",
            entity_type="home",
            entity_id=home.id,
        )
    try:
        challenge = None
        if current_app.config["EMAIL_VERIFICATION_REQUIRED"]:
            challenge, otp = _new_challenge(
                db, user=user, email=email, purpose="email_verification"
            )
            send_otp_email(
                recipient=email,
                otp=otp,
                purpose="email_verification",
                user_name=name,
            )
        db.commit()
    except EmailDeliveryError as error:
        db.rollback()
        return _auth_error(str(error), 503)
    except IntegrityError:
        db.rollback()
        return _auth_error("Unable to create the account with those details.", 409)
    if current_app.config["EMAIL_VERIFICATION_REQUIRED"]:
        if request.is_json:
            return jsonify(
                verification_required=True,
                email=email,
                message="Check your email for a verification code.",
            ), 202
        return redirect(
            url_for(
                "auth.verify_email_page",
                email=email,
                next=request.args.get("next", ""),
            )
        )
    session.clear()
    session["user_id"] = user.id
    session["session_version"] = user.session_version
    session.permanent = True
    csrf_token()
    if request.is_json:
        return jsonify(user={"id": user.id, "email": user.email, "display_name": user.display_name}, home={"id": home.id, "name": home.name}), 201
    return redirect(url_for("alerts.alerts_page"))


@auth.post("/api/auth/verify-email")
@auth.post("/verify-email")
def verify_email():
    try:
        payload = _payload()
        _csrf(payload)
        email = validate_email(payload.get("email"))
        if not _email_rate_limit("verify-email", email, ip_limit=20, email_limit=10):
            raise AuthInputError("Too many verification attempts. Request a new code later.")
        otp = payload.get("otp")
        db = get_session()
        challenge = _verify_challenge(db, email=email, purpose="email_verification", otp=otp)
        user = db.get(User, challenge.user_id)
        if user is None:
            raise AuthInputError("That code is invalid or has expired.")
        if not user.is_active:
            raise AuthInputError("This account is disabled. Contact an administrator.")
        user.email_verified_at = datetime.now(timezone.utc)
        if not db.scalar(
            select(HomeMembership.home_id).where(HomeMembership.user_id == user.id)
        ):
            home = Home(id=str(uuid.uuid4()), name=f"{user.display_name}'s home")
            db.add_all(
                [
                    home,
                    HomeMembership(home_id=home.id, user_id=user.id, role="owner"),
                ]
            )
            db.flush()
            record_event(
                db,
                home_id=home.id,
                actor_user_id=user.id,
                event_type="account.registered",
                entity_type="home",
                entity_id=home.id,
            )
        db.commit()
    except (AuthInputError, ValueError, TypeError) as error:
        get_session().rollback()
        return _auth_error(str(error), 400)
    if request.is_json:
        return jsonify(verified=True)
    next_url = request.form.get("next", "")
    return redirect(url_for("auth.login_page", next=next_url) if next_url else url_for("auth.login_page"))


@auth.post("/api/auth/verify-email/resend")
@auth.post("/verify-email/resend")
def resend_verification():
    try:
        payload = _payload()
        _csrf(payload)
        email = validate_email(payload.get("email"))
        if not _email_rate_limit("resend-verification", email, ip_limit=10, email_limit=5):
            return jsonify(message="If the account can be verified, a new code has been sent.")
        db = get_session()
        user = db.scalar(
            select(User).where(
                User.email == email,
                User.is_active.is_(True),
                User.email_verified_at.is_(None),
            )
        )
        if user is None:
            return jsonify(message="If the account can be verified, a new code has been sent.")
        _, otp = _new_challenge(db, user=user, email=email, purpose="email_verification")
        send_otp_email(
            recipient=email,
            otp=otp,
            purpose="email_verification",
            user_name=user.display_name,
        )
        db.commit()
    except (AuthInputError, ValueError, TypeError, EmailDeliveryError) as error:
        get_session().rollback()
        return jsonify(error=str(error)), 400 if not isinstance(error, EmailDeliveryError) else 503
    return jsonify(message="If the account can be verified, a new code has been sent.")


@auth.post("/api/auth/forgot-password")
@auth.post("/forgot-password")
def forgot_password():
    generic = "If an account matches that email, a reset code has been sent."
    try:
        payload = _payload()
        _csrf(payload)
        email = validate_email(payload.get("email"))
        if not _email_rate_limit("forgot-password", email, ip_limit=10, email_limit=3):
            return jsonify(message=generic)
        db = get_session()
        user = db.scalar(select(User).where(User.email == email))
        if user is not None:
            _, otp = _new_challenge(db, user=user, email=email, purpose="password_reset")
            send_otp_email(
                recipient=email,
                otp=otp,
                purpose="password_reset",
                user_name=user.display_name,
            )
            db.commit()
    except (AuthInputError, ValueError, TypeError, EmailDeliveryError) as error:
        get_session().rollback()
        if isinstance(error, EmailDeliveryError):
            return jsonify(error="Unable to send the reset email. Please try again later."), 503
    if request.is_json:
        return jsonify(message=generic)
    return render_template("auth/verify_reset.html", csrf_token=csrf_token(), error=None, message=generic)


@auth.post("/api/auth/verify-reset")
def verify_reset():
    try:
        payload = _payload()
        _csrf(payload)
        email = validate_email(payload.get("email"))
        if not _email_rate_limit("verify-reset", email, ip_limit=20, email_limit=10):
            raise AuthInputError("That code is invalid or has expired.")
        db = get_session()
        challenge = _verify_challenge(db, email=email, purpose="password_reset", otp=payload.get("otp"))
        reset_token = secrets.token_urlsafe(32)
        challenge.reset_token_hash = _reset_token_hash(reset_token)
        challenge.reset_token_expires_at = datetime.now(timezone.utc) + timedelta(
            seconds=current_app.config["RESET_TOKEN_EXPIRY_SECONDS"]
        )
        db.commit()
    except (AuthInputError, ValueError, TypeError) as error:
        get_session().rollback()
        return jsonify(error=str(error)), 400
    return jsonify(reset_token=reset_token)


@auth.post("/api/auth/reset-password")
@auth.post("/reset-password")
def reset_password():
    try:
        payload = _payload()
        _csrf(payload)
        token = payload.get("reset_token")
        password = payload.get("password")
        validate_password(password)
        db = get_session()
        now = datetime.now(timezone.utc)
        claim = db.execute(
            update(EmailChallenge)
            .where(
                EmailChallenge.reset_token_hash == _reset_token_hash(token),
                EmailChallenge.purpose == "password_reset",
                EmailChallenge.reset_token_used_at.is_(None),
            )
            .values(reset_token_used_at=now)
        )
        if claim.rowcount != 1:
            raise AuthInputError("Reset verification is required.")
        db.flush()
        challenge = db.scalar(
            select(EmailChallenge).where(
                EmailChallenge.reset_token_hash == _reset_token_hash(token),
                EmailChallenge.purpose == "password_reset",
            )
        )
        if (
            challenge is None
            or challenge.consumed_at is None
            or challenge.reset_token_expires_at is None
            or _aware(challenge.reset_token_expires_at) <= now
            or challenge.user_id is None
        ):
            raise AuthInputError("Reset verification is required.")
        user = db.get(User, challenge.user_id)
        if user is None:
            raise AuthInputError("Reset verification is required.")
        user.password_hash = hash_password(password)
        user.session_version += 1
        _record_user_auth_event(
            db,
            user.id,
            "account.password_reset",
            actor_user_id=user.id,
        )
        db.commit()
    except (AuthInputError, ValueError, TypeError) as error:
        get_session().rollback()
        return _auth_error(str(error), 400)
    if request.is_json:
        return jsonify(status="password_reset")
    return redirect(url_for("auth.login_page"))


@auth.post("/api/auth/login")
@auth.post("/login")
def login():
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

    if _login_failure_rate_limited(email):
        return _auth_error("Too many sign-in attempts. Try again later.", 429)

    user = get_session().scalar(select(User).where(User.email == email))
    if user is None or not verify_password(
        user.password_hash if user else _DUMMY_PASSWORD_HASH, password
    ):
        if not _record_login_failure(email):
            return _auth_error("Too many sign-in attempts. Try again later.", 429)
        if user is not None:
            _record_user_auth_event(
                get_session(),
                user.id,
                "account.login_failed",
                {"reason": "invalid_credentials"},
            )
            get_session().commit()
        return _auth_error("Email or password is incorrect.", 401)
    if not user.is_active:
        return _auth_error("This account is disabled.", 403)
    if current_app.config["EMAIL_VERIFICATION_REQUIRED"] and user.email_verified_at is None:
        return _auth_error(
            "Verify your email before signing in. Request a new code if needed.",
            403,
        )
    db = get_session()
    _record_user_auth_event(
        db, user.id, "account.login_succeeded", actor_user_id=user.id
    )
    db.commit()
    session.clear()
    session["user_id"] = user.id
    session["session_version"] = user.session_version
    session.permanent = True
    csrf_token()
    if request.is_json:
        return jsonify(user={"id": user.id, "email": user.email, "display_name": user.display_name})
    next_url = request.args.get("next", "")
    if next_url and urlsplit(next_url).path == url_for("landing"):
        next_url = ""
    if next_url.startswith("/") and not next_url.startswith("//"):
        return redirect(next_url)
    return redirect(url_for("alerts.alerts_page"))


@auth.post("/api/auth/logout")
@auth.post("/logout")
def logout():
    user = current_user()
    if user is None:
        return jsonify(error="Authentication is required."), 401
    from app.security.sessions import verify_csrf

    verify_csrf()
    db = get_session()
    _record_user_auth_event(
        db, user.id, "account.logged_out", actor_user_id=user.id
    )
    db.commit()
    session.clear()
    if request.is_json or request.path.startswith("/api/"):
        return jsonify(status="signed_out")
    return redirect(url_for("landing"))