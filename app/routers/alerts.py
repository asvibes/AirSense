import hmac
import math
from datetime import datetime, timezone
from typing import Any

from flask import (
    Blueprint,
    current_app,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from werkzeug.exceptions import BadRequest
from sqlalchemy import func, select

from app.db import get_session
from app.models.alert import Alert
from app.models.home import Home
from app.models.room import Room
from app.security.sessions import (
    current_user,
    list_user_homes,
    require_home_role,
    require_user,
)
from app.services.audit import record_event
from app.repositories.alerts import (
    AlertNotFound,
    InvalidAlertTransition,
    InvalidReading,
    acknowledge_alert,
    configure_policy,
    list_alerts,
    list_latest_readings,
    process_reading,
)


alerts = Blueprint("alerts", __name__)


@alerts.before_request
def require_api_token():
    if (
        not current_app.config["REQUIRE_API_TOKEN"]
        or request.endpoint
        in {"health", "static", "alerts.index", "alerts.alerts_page"}
        or session.get("user_id")
    ):
        return None
    expected = current_app.config["API_TOKEN"]
    supplied = request.headers.get("Authorization", "")
    if not expected:
        return jsonify(error="Requests are disabled until AIRSENSE_API_TOKEN is configured."), 503
    if len(expected) < 32:
        return jsonify(error="AIRSENSE_API_TOKEN must contain at least 32 characters."), 503
    if not hmac.compare_digest(supplied.encode("utf-8"), expected.encode("utf-8")):
        return jsonify(error="A valid bearer token is required."), 401
    return None


@alerts.get("/")
def index():
    return redirect(url_for("alerts.alerts_page"))


@alerts.get("/alerts")
@require_user(api=False)
def alerts_page():
    user = current_user()
    home_rows = list_user_homes(user.id)
    if not home_rows:
        return redirect(url_for("auth.login_page"))
    requested_home = request.args.get("home_id") or session.get("home_id")
    selected = next((home for home in home_rows if home["id"] == requested_home), home_rows[0])
    session["home_id"] = selected["id"]
    return render_template(
        "alerts.html",
        error=request.args.get("error"),
        notice=request.args.get("notice"),
        high_threshold=current_app.config["HIGH_THRESHOLD"],
        elevated_threshold=current_app.config["ELEVATED_THRESHOLD"],
        api_token_required=current_app.config["REQUIRE_API_TOKEN"],
        current_user=user,
        homes=home_rows,
        active_home=selected,
        csrf_token=_csrf_token(),
    )


def _csrf_token() -> str:
    from app.security.sessions import csrf_token

    return csrf_token()


@alerts.get("/api/dashboard")
@require_user()
def api_dashboard():
    try:
        home_id = request.args.get("home_id") or session.get("home_id")
        if not isinstance(home_id, str) or not home_id:
            return jsonify(error="Select a home first."), 400
        require_home_role(home_id, "owner", "member")
    except ValueError as error:
        return _request_error(str(error), 400)
    session = get_session()
    return jsonify(
        home_id=home_id,
        readings=list_latest_readings(session, home_id),
        alerts=list_alerts(session, home_id),
    )


@alerts.get("/api/alerts")
@require_user()
def api_alerts():
    home_id = request.args.get("home_id") or session.get("home_id")
    if not home_id:
        return jsonify(error="Select a home first."), 400
    require_home_role(home_id, "owner", "member")
    return jsonify(alerts=list_alerts(get_session(), home_id))


@alerts.post("/api/policies")
@require_user()
def update_policy():
    try:
        payload = _request_payload()
        home_id = payload.get("home_id") or session.get("home_id")
        if not isinstance(home_id, str) or not home_id:
            raise ValueError("Select a home first.")
        require_home_role(home_id, "owner")
        room_name = _required_text(payload, "room", 100)
        room = get_session().scalar(
            select(Room).where(
                Room.home_id == home_id,
                func.lower(Room.name) == room_name.casefold(),
            )
        )
        if room is None:
            return _request_error("Room was not found in this home.", 404)
        values = {
            "high_threshold": _number(payload, "high_threshold"),
            "elevated_threshold": _number(payload, "elevated_threshold"),
            "elevated_duration_seconds": _integer(
                payload, "elevated_duration_seconds"
            ),
            "rapid_rise_per_minute": _number(payload, "rapid_rise_per_minute"),
            "all_clear_duration_seconds": _integer(
                payload, "all_clear_duration_seconds"
            ),
            "max_reading_gap_seconds": _integer(
                payload, "max_reading_gap_seconds"
            ),
        }
        policy = configure_policy(
            get_session(),
            home_id=home_id,
            home_name="",
            room_name=room.name,
            metric_code=_text(payload, "metric", "CO2", 32),
            unit=_text(payload, "unit", "ppm", 24),
            values=values,
        )
        record_event(
            get_session(),
            home_id=home_id,
            actor_user_id=current_user().id,
            event_type="threshold.updated",
            entity_type="threshold",
            entity_id=f"{room.id}:{policy['metric']}",
            details=values,
        )
        get_session().commit()
    except (TypeError, ValueError) as error:
        return _request_error(str(error), 400)
    return jsonify(policy=policy)


@alerts.post("/api/readings")
@alerts.post("/readings")
@require_user()
def submit_reading():
    try:
        payload = _request_payload()
        home_id = payload.get("home_id") or session.get("home_id")
        if not isinstance(home_id, str) or not home_id:
            raise ValueError("Select a home first.")
        require_home_role(home_id, "owner", "member")
        home = get_session().get(Home, home_id)
        room_name = _required_text(payload, "room", 100)
        room = get_session().scalar(
            select(Room).where(
                Room.home_id == home_id,
                func.lower(Room.name) == room_name.casefold(),
            )
        )
        if home is None or room is None:
            return _request_error("Home or room was not found.", 404)
        reading = process_reading(
            get_session(),
            home_id=home_id,
            home_name=home.name,
            room_name=room.name,
            metric_code=_text(payload, "metric", "CO2", 32),
            unit=_text(payload, "unit", "ppm", 24),
            value=_number(payload, "value", payload.get("co2_ppm")),
            source="simulated",
            measured_at=_timestamp(payload.get("measured_at")),
            defaults=_policy_defaults(),
            max_future_seconds=current_app.config["MAX_FUTURE_SECONDS"],
        )
        record_event(
            get_session(),
            home_id=home_id,
            actor_user_id=current_user().id,
            event_type="reading.ingested",
            entity_type="reading",
            entity_id=str(reading["reading_id"]),
            details={"source": "simulated", "metric": reading["metric"]},
        )
        get_session().commit()
    except (TypeError, ValueError) as error:
        return _request_error(str(error), 400)

    if _wants_json():
        return jsonify(reading), 201
    notice = "Reading saved. " + (
        f"{len(reading['created'])} alert(s) opened."
        if reading["created"]
        else f"{len(reading['cleared'])} alert(s) now all clear."
        if reading["cleared"]
        else "No alert state changed."
    )
    return redirect(url_for("alerts.alerts_page", notice=notice))


@alerts.post("/api/alerts/<int:alert_id>/acknowledge")
@alerts.post("/alerts/<int:alert_id>/acknowledge")
@require_user()
def acknowledge(alert_id: int):
    try:
        _request_payload()
        alert_row = get_session().get(Alert, alert_id)
        if alert_row is None:
            raise AlertNotFound(f"Alert {alert_id} was not found.")
        require_home_role(alert_row.home_id, "owner", "member")
        actor = current_user()
        alert = acknowledge_alert(get_session(), alert_id, actor.display_name)
        record_event(
            get_session(),
            home_id=alert_row.home_id,
            actor_user_id=actor.id,
            event_type="alert.acknowledged",
            entity_type="alert",
            entity_id=str(alert_id),
        )
        get_session().commit()
    except InvalidAlertTransition as error:
        return _request_error(str(error), 409)
    except AlertNotFound as error:
        return _request_error(str(error), 404)
    except (TypeError, ValueError) as error:
        return _request_error(str(error), 400)

    if _wants_json():
        return jsonify(alert=alert)
    return redirect(url_for("alerts.alerts_page", notice="Alert acknowledged."))


def _request_payload() -> dict[str, Any]:
    if request.is_json:
        try:
            payload = request.get_json()
        except BadRequest as error:
            raise ValueError("Request body must contain valid JSON.") from error
        if not isinstance(payload, dict):
            raise ValueError("JSON request body must be an object.")
        return payload
    return request.form


def _text(payload, field: str, default: str, max_length: int) -> str:
    value = payload.get(field, default)
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > max_length:
        raise ValueError(f"{field} must contain 1 to {max_length} characters.")
    return value.strip()


def _required_text(payload, field: str, max_length: int) -> str:
    value = payload.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} is required.")
    if len(value.strip()) > max_length:
        raise ValueError(f"{field} must be {max_length} characters or fewer.")
    return value.strip()


def _number(payload, field: str, fallback: Any = None) -> float:
    value = payload.get(field, fallback)
    if isinstance(value, bool):
        raise ValueError(f"{field} must be a number.")
    try:
        number = float(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{field} must be a number.") from error
    if not math.isfinite(number) or number < 0:
        raise ValueError(f"{field} must be a finite non-negative number.")
    return number


def _integer(payload, field: str) -> int:
    value = payload.get(field)
    if isinstance(value, bool):
        raise ValueError(f"{field} must be a whole number.")
    try:
        number = float(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{field} must be a whole number.") from error
    if not math.isfinite(number) or not number.is_integer():
        raise ValueError(f"{field} must be a whole number.")
    return int(number)


def _timestamp(value: Any) -> datetime:
    if value is None:
        return datetime.now(timezone.utc)
    if not isinstance(value, str):
        raise ValueError("measured_at must be an ISO-8601 timestamp.")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError("measured_at must be an ISO-8601 timestamp.") from error
    if parsed.tzinfo is None:
        raise ValueError("measured_at must include a timezone.")
    return parsed.astimezone(timezone.utc)


def _policy_defaults() -> dict:
    return {
        "high_threshold": current_app.config["HIGH_THRESHOLD"],
        "elevated_threshold": current_app.config["ELEVATED_THRESHOLD"],
        "elevated_duration_seconds": current_app.config[
            "ELEVATED_DURATION_SECONDS"
        ],
        "rapid_rise_per_minute": current_app.config["RAPID_RISE_PER_MINUTE"],
        "all_clear_duration_seconds": current_app.config[
            "ALL_CLEAR_DURATION_SECONDS"
        ],
        "max_reading_gap_seconds": current_app.config[
            "MAX_READING_GAP_SECONDS"
        ],
    }


def _wants_json() -> bool:
    return request.path.startswith("/api/") or request.is_json


def _request_error(message: str, status: int):
    if _wants_json():
        return jsonify(error=message), status
    return redirect(url_for("alerts.alerts_page", error=message), code=303)