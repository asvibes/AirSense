from flask import Blueprint, current_app, jsonify, request
from sqlalchemy import select

from app.db import get_session
from app.models.metric import Metric
from app.models.room import Room
from app.models.threshold import ThresholdPolicy
from app.repositories.alerts import InvalidReading, configure_policy
from app.security.sessions import current_user, require_home_role, require_user
from app.services.audit import record_event


thresholds = Blueprint("thresholds", __name__)


@thresholds.get("/api/homes/<home_id>/thresholds")
@require_user()
def list_thresholds(home_id: str):
    require_home_role(home_id, "owner", "member")
    db = get_session()
    rows = db.execute(
        select(ThresholdPolicy, Room.name, Metric.unit)
        .join(Room, ThresholdPolicy.room_id == Room.id)
        .join(Metric, ThresholdPolicy.metric_code == Metric.code)
        .where(ThresholdPolicy.home_id == home_id)
        .order_by(Room.name, ThresholdPolicy.metric_code)
    )
    return jsonify(
        thresholds=[
            {
                "room_id": policy.room_id,
                "room": room_name,
                "metric": policy.metric_code,
                "unit": unit,
                "high_threshold": policy.high_threshold,
                "elevated_threshold": policy.elevated_threshold,
                "elevated_duration_seconds": policy.elevated_duration_seconds,
                "rapid_rise_per_minute": policy.rapid_rise_per_minute,
                "all_clear_duration_seconds": policy.all_clear_duration_seconds,
                "max_reading_gap_seconds": policy.max_reading_gap_seconds,
            }
            for policy, room_name, unit in rows
        ]
    )


@thresholds.put("/api/homes/<home_id>/thresholds")
@require_user()
def update_thresholds(home_id: str):
    require_home_role(home_id, "owner")
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict) or not isinstance(payload.get("thresholds"), list):
        return jsonify(error="thresholds must be a list of room settings."), 400
    requested = payload["thresholds"]
    if not requested:
        return jsonify(error="At least one room threshold is required."), 400
    if len(requested) > 100:
        return jsonify(error="A maximum of 100 room thresholds can be saved at once."), 400

    db = get_session()
    try:
        updates = []
        seen_rooms = set()
        for item in requested:
            if not isinstance(item, dict):
                raise ValueError("Each threshold entry must be an object.")
            room_id = item.get("room_id")
            if not isinstance(room_id, str) or not room_id or room_id in seen_rooms:
                raise ValueError("Each room_id must be unique and valid.")
            seen_rooms.add(room_id)
            room = db.scalar(
                select(Room).where(Room.id == room_id, Room.home_id == home_id)
            )
            metric = db.get(Metric, "CO2")
            if room is None or metric is None:
                raise ValueError("Room or CO₂ metric was not found.")
            values = {
                "high_threshold": _number(item, "high_threshold"),
                "elevated_threshold": _number(item, "elevated_threshold"),
                "elevated_duration_seconds": _integer(item, "elevated_duration_seconds"),
                "rapid_rise_per_minute": _number(item, "rapid_rise_per_minute"),
                "all_clear_duration_seconds": _integer(item, "all_clear_duration_seconds"),
                "max_reading_gap_seconds": _integer(item, "max_reading_gap_seconds"),
            }
            updates.append((room, metric, values))

        results = []
        for room, metric, values in updates:
            result = configure_policy(
                db,
                home_id=home_id,
                home_name="",
                room_name=room.name,
                metric_code=metric.code,
                unit=metric.unit,
                values=values,
            )
            record_event(
                db,
                home_id=home_id,
                actor_user_id=current_user().id,
                event_type="threshold.updated",
                entity_type="threshold",
                entity_id=f"{room.id}:{metric.code}",
                details=values,
            )
            results.append(result)
        db.commit()
        return jsonify(thresholds=results)
    except (TypeError, ValueError, InvalidReading) as error:
        db.rollback()
        return jsonify(error=str(error)), 400


@thresholds.put("/api/homes/<home_id>/thresholds/<room_id>/<metric_code>")
@require_user()
def update_threshold(home_id: str, room_id: str, metric_code: str):
    require_home_role(home_id, "owner")
    payload = request.get_json(silent=True) or {}
    try:
        values = {
            "high_threshold": _number(payload, "high_threshold"),
            "elevated_threshold": _number(payload, "elevated_threshold"),
            "elevated_duration_seconds": _integer(payload, "elevated_duration_seconds"),
            "rapid_rise_per_minute": _number(payload, "rapid_rise_per_minute"),
            "all_clear_duration_seconds": _integer(payload, "all_clear_duration_seconds"),
            "max_reading_gap_seconds": _integer(payload, "max_reading_gap_seconds"),
        }
        db = get_session()
        room = db.scalar(
            select(Room).where(Room.id == room_id, Room.home_id == home_id)
        )
        metric = db.get(Metric, metric_code.upper())
        if room is None or metric is None:
            return jsonify(error="Room or metric was not found."), 404
        result = configure_policy(
            db,
            home_id=home_id,
            home_name="",
            room_name=room.name,
            metric_code=metric.code,
            unit=metric.unit,
            values=values,
        )
        record_event(
            db,
            home_id=home_id,
            actor_user_id=current_user().id,
            event_type="threshold.updated",
            entity_type="threshold",
            entity_id=f"{room_id}:{metric.code}",
            details=values,
        )
        db.commit()
        return jsonify(threshold=result)
    except (TypeError, ValueError, InvalidReading) as error:
        get_session().rollback()
        return jsonify(error=str(error)), 400


def _number(payload: dict, field: str) -> float:
    value = payload.get(field)
    if isinstance(value, bool):
        raise ValueError(f"{field} must be a positive number.")
    try:
        result = float(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{field} must be a positive number.") from error
    import math

    if not math.isfinite(result) or result <= 0:
        raise ValueError(f"{field} must be a positive finite number.")
    return result


def _integer(payload: dict, field: str) -> int:
    value = payload.get(field)
    if isinstance(value, bool):
        raise ValueError(f"{field} must be a positive whole number.")
    try:
        result = int(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{field} must be a positive whole number.") from error
    if result <= 0 or str(value).strip() != str(result):
        raise ValueError(f"{field} must be a positive whole number.")
    return result