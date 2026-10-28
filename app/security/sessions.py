import hmac
import secrets
from functools import wraps
from typing import Callable

from flask import abort, g, jsonify, redirect, request, session, url_for
from sqlalchemy import select

from app.db import get_session
from app.models.home import Home
from app.models.user import HomeMembership, User


def current_user() -> User | None:
    if "airsense_user" not in g:
        user_id = session.get("user_id")
        g.airsense_user = get_session().get(User, user_id) if user_id else None
    return g.airsense_user


def csrf_token() -> str:
    token = session.get("csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        session["csrf_token"] = token
    return token


def verify_csrf() -> None:
    expected = session.get("csrf_token")
    supplied = request.headers.get("X-CSRF-Token") or request.form.get("csrf_token")
    if not expected or not supplied or not hmac.compare_digest(expected, supplied):
        abort(400, description="A valid CSRF token is required.")


def require_user(*, api: bool = True) -> Callable:
    def decorate(view: Callable) -> Callable:
        @wraps(view)
        def wrapped(*args, **kwargs):
            user = current_user()
            if user is None or not user.is_active:
                if api or request.path.startswith("/api/"):
                    return jsonify(error="Authentication is required."), 401
                return redirect(url_for("auth.login_page", next=request.full_path))
            if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
                verify_csrf()
            return view(*args, **kwargs)

        return wrapped

    return decorate


def home_membership(home_id: str) -> HomeMembership | None:
    user = current_user()
    if not user:
        return None
    return get_session().get(HomeMembership, (home_id, user.id))


def require_home_role(home_id: str, *roles: str) -> HomeMembership:
    membership = home_membership(home_id)
    if membership is None:
        abort(404)
    if roles and membership.role not in roles:
        abort(403)
    return membership


def list_user_homes(user_id: str) -> list[dict]:
    rows = get_session().execute(
        select(Home, HomeMembership.role)
        .join(HomeMembership, HomeMembership.home_id == Home.id)
        .where(HomeMembership.user_id == user_id)
        .order_by(Home.name)
    ).all()
    return [{"id": home.id, "name": home.name, "role": role} for home, role in rows]