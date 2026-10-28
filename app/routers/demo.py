from flask import Blueprint, current_app, jsonify, request
from sqlalchemy import select

from app.db import get_session
from app.models.room import Room
from app.security.sessions import current_user, require_home_role, require_user
from app.services.ingestion.ingest import ingest_reading
from app.sources.simulator import build_simulated_reading


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
        simulated_reading = build_simulated_reading(
            room=room.name,
            scenario=payload.get("scenario"),
            value=payload.get("value", payload.get("co2_ppm")),
            metric=payload.get("metric", "CO2"),
            unit=payload.get("unit", "ppm"),
            measured_at=payload.get("measured_at"),
        )
        result = ingest_reading(
            get_session(),
            home_id=home_id,
            home_name="",
            payload=simulated_reading,
            source="simulated",
            defaults=_policy_defaults(),
            max_future_seconds=current_app.config["MAX_FUTURE_SECONDS"],
            actor_user_id=current_user().id,
        )
    except ValueError as error:
        get_session().rollback()
        return jsonify(error=str(error)), 400
    return jsonify(result), 201


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