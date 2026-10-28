from datetime import datetime, timezone

from flask import Blueprint, current_app, jsonify, request
from sqlalchemy import select

from app.db import get_session
from app.models.room import Room
from app.repositories.alerts import process_reading
from app.security.sessions import current_user, require_home_role, require_user
from app.services.audit import record_event


demo = Blueprint("demo", __name__)


@demo.post("/api/homes/<home_id>/demo/readings")
@require_user()
def submit_demo_reading(home_id: str):
    require_home_role(home_id, "owner", "member")
    payload = request.get_json(silent=True) or {}
    room_id = payload.get("room_id")
    room = get_session().scalar(
        select(Room).where(Room.id == room_id, Room.home_id == home_id)
    )
    if room is None:
        return jsonify(error="room_id was not found in this home."), 404
    try:
        result = process_reading(
            get_session(),
            home_id=home_id,
            home_name="",
            room_name=room.name,
            metric_code=payload.get("metric", "CO2"),
            unit=payload.get("unit", "ppm"),
            value=_number(payload.get("value")),
            source="simulated",
            measured_at=datetime.now(timezone.utc),
            defaults=_policy_defaults(),
            max_future_seconds=current_app.config["MAX_FUTURE_SECONDS"],
        )
    except ValueError as error:
        get_session().rollback()
        return jsonify(error=str(error)), 400
    record_event(
        get_session(),
        home_id=home_id,
        actor_user_id=current_user().id,
        event_type="demo.reading_submitted",
        entity_type="reading",
        entity_id=str(result["reading_id"]),
        details={"room": room.name, "metric": result["metric"]},
    )
    get_session().commit()
    return jsonify(result), 201


def _number(value) -> float:
    import math

    if isinstance(value, bool):
        raise ValueError("value must be a finite non-negative number.")
    try:
        parsed = float(value)
    except (TypeError, ValueError) as error:
        raise ValueError("value must be a finite non-negative number.") from error
    if not math.isfinite(parsed) or parsed < 0:
        raise ValueError("value must be a finite non-negative number.")
    return parsed


def _policy_defaults() -> dict:
    config = current_app.config
    return {
        "high_threshold": config["HIGH_THRESHOLD"],
        "elevated_threshold": config["ELEVATED_THRESHOLD"],
        "elevated_duration_seconds": config["ELEVATED_DURATION_SECONDS"],
        "rapid_rise_per_minute": config["RAPID_RISE_PER_MINUTE"],
        "all_clear_duration_seconds": config["ALL_CLEAR_DURATION_SECONDS"],
        "max_reading_gap_seconds": config["MAX_READING_GAP_SECONDS"],
    }