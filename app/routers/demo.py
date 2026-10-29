import csv
from datetime import datetime, timezone
from io import StringIO

from flask import Blueprint, current_app, jsonify, request
from sqlalchemy import select
from werkzeug.utils import secure_filename

from app.db import get_session
from app.models.room import Room
from app.security.sessions import current_user, require_home_role, require_user
from app.services.ingestion.ingest import ingest_reading
from app.sources.dalton_replay import load_dalton_csv
from app.sources.simulator import build_simulated_reading


demo = Blueprint("demo", __name__)


@demo.post("/api/homes/<home_id>/demo/readings")
@require_user()
def submit_demo_reading(home_id: str):
    require_home_role(home_id, "owner", "member")
    payload = request.get_json(silent=True)
    if payload is None:
        payload = request.form
    if not hasattr(payload, "get"):
        return jsonify(error="Reading body must be a JSON object."), 400
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


@demo.post("/api/homes/<home_id>/demo/replay")
@require_user()
def submit_dalton_replay(home_id: str):
    require_home_role(home_id, "owner", "member")
    payload = request.get_json(silent=True)
    if payload is None:
        payload = request.form
    if not hasattr(payload, "get"):
        return jsonify(error="Replay request must be an object or multipart form."), 400
    room_id = payload.get("room_id")
    room = get_session().scalar(
        select(Room).where(Room.id == room_id, Room.home_id == home_id)
    )
    if room is None:
        return jsonify(error="room_id was not found in this home."), 404

    csv_file = request.files.get("csv_file")
    if csv_file is None or not csv_file.filename:
        return jsonify(error="Choose a DALTON CSV file to replay."), 400

    try:
        raw_limit = payload.get("limit", "250")
        if isinstance(raw_limit, bool):
            raise ValueError("limit must be a whole number between 1 and 1000.")
        limit = int(raw_limit)
        if str(raw_limit).strip() != str(limit) or not 1 <= limit <= 1000:
            raise ValueError("limit must be a whole number between 1 and 1000.")

        csv_content = csv_file.read().decode("utf-8-sig")
        rows = load_dalton_csv(
            StringIO(csv_content),
            room_name=room.name,
            limit=limit,
            valid_co2_only=True,
        )
    except (OSError, TypeError, UnicodeDecodeError, ValueError, csv.Error) as error:
        return jsonify(error=str(error)), 400

    if not rows:
        return jsonify(error="The CSV contains no valid CO2 readings to replay."), 400

    shift_timestamps = payload.get("shift_timestamps", "true")
    if isinstance(shift_timestamps, str):
        if shift_timestamps.strip().lower() not in {"true", "false", "1", "0"}:
            return jsonify(error="shift_timestamps must be true or false."), 400
        shift_timestamps = shift_timestamps.strip().lower() in {"true", "1"}
    elif not isinstance(shift_timestamps, bool):
        return jsonify(error="shift_timestamps must be true or false."), 400

    if shift_timestamps:
        latest_timestamp = datetime.fromisoformat(rows[-1]["measured_at"])
        offset = datetime.now(timezone.utc) - latest_timestamp
        for row in rows:
            measured_at = datetime.fromisoformat(row["measured_at"])
            row["measured_at"] = (measured_at + offset).isoformat()

    session = get_session()
    created = []
    for row in rows:
        try:
            created.append(
                ingest_reading(
                    session,
                    home_id=home_id,
                    home_name="",
                    payload=row,
                    source="dataset",
                    defaults=_policy_defaults(),
                    max_future_seconds=current_app.config["MAX_FUTURE_SECONDS"],
                    actor_user_id=current_user().id,
                )
            )
        except ValueError as error:
            session.rollback()
            return jsonify(error=f"Failed on DALTON row: {error}"), 400

    session.commit()
    return jsonify(
        {
            "source": "dalton_replay",
            "source_file": secure_filename(csv_file.filename) or "uploaded.csv",
            "imported": len(created),
            "timestamps_shifted": shift_timestamps,
            "room_id": room.id,
            "room": room.name,
            "created": created,
        }
    ), 201


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