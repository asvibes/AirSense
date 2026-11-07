import csv
from datetime import datetime, timezone
from io import StringIO

from flask import Blueprint, current_app, jsonify, request
from sqlalchemy import select
from werkzeug.utils import secure_filename

from app.db import get_session
from app.models.reading import Reading
from app.models.room import Room
from app.security.sessions import current_user, require_home_role, require_user
from app.services.ingestion.ingest import ingest_reading
from app.services.ingestion.rejections import record_rejection
from app.sources.dalton_replay import parse_environmental_csv
from app.sources.simulator import build_simulated_reading
from app.timestamps import format_utc


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
        session = get_session()
        session.rollback()
        record_rejection(
            session,
            home_id=home_id,
            sensor_id=None,
            source="simulated",
            actor_user_id=current_user().id,
        )
        session.commit()
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
        return jsonify(error="Choose a CSV file to import."), 400

    try:
        raw_limit = payload.get("limit", "250")
        if isinstance(raw_limit, bool):
            raise ValueError("limit must be a whole number between 1 and 1000.")
        limit = int(raw_limit)
        if str(raw_limit).strip() != str(limit) or not 1 <= limit <= 1000:
            raise ValueError("limit must be a whole number between 1 and 1000.")

        csv_content = csv_file.read().decode("utf-8-sig")
        csv_headers = next(csv.reader(StringIO(csv_content)), [])
        normalized_headers = {
            header.strip().lstrip("\ufeff").casefold() for header in csv_headers
        }
        dataset = parse_environmental_csv(
            StringIO(csv_content),
            room_name=room.name,
            limit=limit,
            valid_only=True,
        )
    except (OSError, TypeError, UnicodeDecodeError, ValueError, csv.Error) as error:
        return jsonify(error=str(error)), 400

    rows = dataset["readings"]
    shift_timestamps = payload.get("shift_timestamps", "false")
    if isinstance(shift_timestamps, str):
        if shift_timestamps.strip().lower() not in {"true", "false", "1", "0"}:
            return jsonify(error="shift_timestamps must be true or false."), 400
        shift_timestamps = shift_timestamps.strip().lower() in {"true", "1"}
    elif not isinstance(shift_timestamps, bool):
        return jsonify(error="shift_timestamps must be true or false."), 400

    if shift_timestamps and rows:
        latest_timestamp = datetime.fromisoformat(
            rows[-1]["measured_at"].replace("Z", "+00:00")
        )
        offset = datetime.now(timezone.utc) - latest_timestamp

        for row in rows:
            measured_at = datetime.fromisoformat(
                row["measured_at"].replace("Z", "+00:00")
            )
            row["measured_at"] = format_utc(measured_at + offset)

    session = get_session()
    existing_rows = []
    if rows:
        metric_codes = {str(row["metric"]) for row in rows}
        timestamps = [datetime.fromisoformat(str(row["measured_at"]).replace("Z", "+00:00")) for row in rows]
        existing_rows = session.scalars(
            select(Reading).where(
                Reading.home_id == home_id,
                Reading.room_id == room.id,
                Reading.metric_code.in_(metric_codes),
                Reading.measured_at >= min(timestamps),
                Reading.measured_at <= max(timestamps),
            )
        ).all()
    existing_keys = {
        (reading.metric_code, format_utc(reading.measured_at))
        for reading in existing_rows
    }
    duplicate_readings = list(dataset["duplicate_readings"])
    existing_duplicates_skipped = 0
    filtered_rows = []
    for row in rows:
        key = (str(row["metric"]), str(row["measured_at"]))
        if key in existing_keys:
            existing_duplicates_skipped += 1
            duplicate_readings.append(
                {"metric": key[0], "measured_at": key[1]}
            )
        else:
            filtered_rows.append(row)
    rows = filtered_rows
    if not rows:
        return jsonify(
            error=(
                "The CSV contained no new supported readings. "
                "Review unsupported columns or duplicate timestamps."
            ),
            imported=0,
            parameters=[],
            review_columns=dataset["review_columns"],
            duplicate_readings=duplicate_readings,
            rows_seen=dataset["rows_seen"],
            rows_skipped=dataset["rows_skipped"] + existing_duplicates_skipped,
            timestamps_shifted=shift_timestamps,
            room_id=room.id,
            room=room.name,
        ), 422

    parameter_counts: dict[str, dict[str, object]] = {}
    for row in rows:
        code = str(row["metric"])
        summary = parameter_counts.setdefault(
            code,
            {
                "code": code,
                "name": row["metric_name"],
                "unit": row["unit"],
                "readings": 0,
            },
        )
        summary["readings"] = int(summary["readings"]) + 1

    created = []
    try:
        with session.begin_nested():
            for row in rows:
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
                        commit=False,
                    )
                )
        session.commit()
    except ValueError as error:
        session.rollback()
        record_rejection(
            session,
            home_id=home_id,
            sensor_id=None,
            source="dataset",
            actor_user_id=current_user().id,
        )
        session.commit()
        return jsonify(error=f"Failed on dataset row: {error}"), 400
    except Exception:
        session.rollback()
        raise
    return jsonify(
        {
            "source": (
                "dalton_replay"
                if {"co2", "valid_co2"}.issubset(normalized_headers)
                else "environmental_csv"
            ),
            "source_file": secure_filename(csv_file.filename) or "uploaded.csv",
            "imported": len(created),
            "parameters": list(parameter_counts.values()),
            "review_columns": dataset["review_columns"],
            "duplicate_readings": duplicate_readings,
            "rows_seen": dataset["rows_seen"],
            "rows_skipped": dataset["rows_skipped"] + existing_duplicates_skipped,
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