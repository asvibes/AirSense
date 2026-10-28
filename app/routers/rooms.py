import uuid

from flask import Blueprint, jsonify, request
from sqlalchemy import select

from app.db import get_session
from app.models.reading import Reading
from app.models.room import Room
from app.models.sensor import Sensor
from app.models.threshold import ThresholdPolicy
from app.security.sessions import current_user, require_home_role, require_user
from app.services.audit import record_event
from app.services.freshness import sensor_freshness


rooms = Blueprint("rooms", __name__)
VENTILATION_SOURCES = {
    "Window",
    "Exhaust fan",
    "Air conditioner",
    "Kitchen chimney",
    "Not specified",
}


@rooms.get("/api/homes/<home_id>/rooms")
@require_user()
def list_rooms(home_id: str):
    require_home_role(home_id, "owner", "member")
    db = get_session()
    room_rows = db.scalars(select(Room).where(Room.home_id == home_id).order_by(Room.name))
    result = []
    for room in room_rows:
        sensors = db.scalars(
            select(Sensor).where(
                Sensor.home_id == home_id, Sensor.room_id == room.id
            )
        ).all()
        readings = db.execute(
            select(Reading)
            .where(Reading.home_id == home_id, Reading.room_id == room.id)
            .order_by(Reading.measured_at.desc(), Reading.id.desc())
            .limit(20)
        ).scalars().all()
        latest_by_metric = {}
        for reading in readings:
            latest_by_metric.setdefault(reading.metric_code, reading)
        policies = db.scalars(
            select(ThresholdPolicy).where(
                ThresholdPolicy.home_id == home_id, ThresholdPolicy.room_id == room.id
            )
        ).all()
        result.append(
            {
                "id": room.id,
                "name": room.name,
                "ventilation": room.ventilation,
                "ventilation_sources": room.ventilation_sources,
                "readings": [
                    {
                        "metric": reading.metric_code,
                        "value": reading.value,
                        "unit": _metric_unit(db, reading.metric_code),
                        "source": reading.source,
                        "measured_at": reading.measured_at.isoformat(),
                    }
                    for reading in latest_by_metric.values()
                ],
                "sensors": [
                    {
                        "id": sensor.id,
                        "name": sensor.name,
                        "status": sensor.status,
                        **sensor_freshness(sensor),
                    }
                    for sensor in sensors
                ],
                "thresholds": [
                    {
                        "metric": policy.metric_code,
                        "high_threshold": policy.high_threshold,
                        "elevated_threshold": policy.elevated_threshold,
                        "elevated_duration_seconds": policy.elevated_duration_seconds,
                        "rapid_rise_per_minute": policy.rapid_rise_per_minute,
                        "all_clear_duration_seconds": policy.all_clear_duration_seconds,
                        "max_reading_gap_seconds": policy.max_reading_gap_seconds,
                    }
                    for policy in policies
                ],
            }
        )
    return jsonify(rooms=result)


@rooms.post("/api/homes/<home_id>/rooms")
@require_user()
def create_room(home_id: str):
    require_home_role(home_id, "owner")
    payload = request.get_json(silent=True) or {}
    name = payload.get("name")
    ventilation_sources = payload.get("ventilation_sources")
    if ventilation_sources is None:
        legacy_value = payload.get("ventilation", "Not specified")
        ventilation_sources = [legacy_value] if isinstance(legacy_value, str) else legacy_value
    if not isinstance(name, str) or not name.strip() or len(name.strip()) > 100:
        return jsonify(error="name must contain 1 to 100 characters."), 400
    if (
        not isinstance(ventilation_sources, list)
        or not ventilation_sources
        or len(ventilation_sources) > len(VENTILATION_SOURCES)
        or any(
            not isinstance(source, str) or source not in VENTILATION_SOURCES
            for source in ventilation_sources
        )
        or len(set(ventilation_sources)) != len(ventilation_sources)
        or ("Not specified" in ventilation_sources and len(ventilation_sources) > 1)
    ):
        return jsonify(
            error="Choose one or more valid ventilation sources. “Not specified” must be selected by itself."
        ), 400
    db = get_session()
    exists = db.scalar(
        select(Room.id).where(
            Room.home_id == home_id, Room.name.ilike(name.strip())
        )
    )
    if exists:
        return jsonify(error="A room with this name already exists."), 409
    room = Room(
        id=str(uuid.uuid4()),
        home_id=home_id,
        name=name.strip(),
        ventilation=", ".join(ventilation_sources),
        ventilation_sources=ventilation_sources,
    )
    db.add(room)
    record_event(
        db,
        home_id=home_id,
        actor_user_id=current_user().id,
        event_type="room.created",
        entity_type="room",
        entity_id=room.id,
        details={"name": room.name},
    )
    db.commit()
    return jsonify(
        room={
            "id": room.id,
            "name": room.name,
            "ventilation": room.ventilation,
            "ventilation_sources": room.ventilation_sources,
        }
    ), 201


def _metric_unit(db, metric_code: str) -> str:
    from app.models.metric import Metric

    metric = db.get(Metric, metric_code)
    return metric.unit if metric else ""