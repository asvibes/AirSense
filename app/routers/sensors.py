import uuid

from flask import Blueprint, current_app, jsonify, request
from sqlalchemy import select

from app.db import get_session
from app.models.room import Room
from app.models.sensor import Sensor
from app.schemas.sensor import validate_sensor_input
from app.security.device_keys import hash_device_key
from app.security.sessions import current_user, require_home_role, require_user
from app.services.audit import record_event
from app.services.freshness import sensor_freshness
from app.services.provisioning import ProvisioningError, create_sensor, revoke_sensor, rotate_sensor_key


sensors = Blueprint("sensors", __name__)


def _pepper() -> str:
    return current_app.config.get("DEVICE_KEY_PEPPER") or current_app.config["SECRET_KEY"]


@sensors.get("/api/homes/<home_id>/sensors")
@require_user()
def list_sensors(home_id: str):
    require_home_role(home_id, "owner", "member")
    rows = get_session().scalars(
        select(Sensor).where(Sensor.home_id == home_id).order_by(Sensor.created_at)
    )
    return jsonify(
        sensors=[
            {
                "id": sensor.id,
                "name": sensor.name,
                "room_id": sensor.room_id,
                "room": sensor.room.name,
                "status": sensor.status,
                **sensor_freshness(sensor),
            }
            for sensor in rows
        ]
    )


@sensors.post("/api/homes/<home_id>/sensors")
@require_user()
def provision_sensor(home_id: str):
    require_home_role(home_id, "owner")
    try:
        name, room_id, interval = validate_sensor_input(request.get_json(silent=True))
        db = get_session()
        sensor, key = create_sensor(
            db,
            home_id=home_id,
            room_id=room_id,
            name=name,
            pepper=_pepper(),
            reporting_interval_seconds=interval,
        )
        record_event(
            db,
            home_id=home_id,
            actor_user_id=current_user().id,
            event_type="sensor.provisioned",
            entity_type="sensor",
            entity_id=sensor.id,
            details={"name": sensor.name, "room_id": room_id},
        )
        db.commit()
    except ProvisioningError as error:
        return jsonify(error=str(error)), 400
    return jsonify(
        sensor={"id": sensor.id, "name": sensor.name, "room_id": sensor.room_id},
        device_key=key,
        warning="Copy this key now. It cannot be retrieved after this response.",
    ), 201


@sensors.post("/api/homes/<home_id>/sensors/<sensor_id>/rotate-key")
@require_user()
def rotate_key(home_id: str, sensor_id: str):
    require_home_role(home_id, "owner")
    db = get_session()
    sensor = db.scalar(
        select(Sensor).where(Sensor.id == sensor_id, Sensor.home_id == home_id)
    )
    if sensor is None:
        return jsonify(error="Sensor not found."), 404
    try:
        key = rotate_sensor_key(db, sensor, _pepper())
    except ProvisioningError as error:
        return jsonify(error=str(error)), 409
    record_event(
        db,
        home_id=home_id,
        actor_user_id=current_user().id,
        event_type="sensor.key_rotated",
        entity_type="sensor",
        entity_id=sensor.id,
    )
    db.commit()
    return jsonify(device_key=key, warning="Copy this key now; it cannot be retrieved again.")


@sensors.post("/api/homes/<home_id>/sensors/<sensor_id>/revoke")
@require_user()
def revoke(home_id: str, sensor_id: str):
    require_home_role(home_id, "owner")
    db = get_session()
    sensor = db.scalar(
        select(Sensor).where(Sensor.id == sensor_id, Sensor.home_id == home_id)
    )
    if sensor is None:
        return jsonify(error="Sensor not found."), 404
    revoke_sensor(sensor)
    record_event(
        db,
        home_id=home_id,
        actor_user_id=current_user().id,
        event_type="sensor.revoked",
        entity_type="sensor",
        entity_id=sensor.id,
    )
    db.commit()
    return jsonify(sensor={"id": sensor.id, "status": sensor.status})