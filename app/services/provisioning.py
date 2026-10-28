import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.room import Room
from app.models.sensor import Sensor
from app.security.device_keys import hash_device_key, issue_device_key


class ProvisioningError(ValueError):
    pass


def create_sensor(
    session: Session,
    *,
    home_id: str,
    room_id: str,
    name: str,
    pepper: str,
    reporting_interval_seconds: int = 300,
) -> tuple[Sensor, str]:
    room = session.scalar(
        select(Room).where(Room.id == room_id, Room.home_id == home_id)
    )
    if room is None:
        raise ProvisioningError("Room was not found in this home.")
    if not name.strip() or len(name.strip()) > 120:
        raise ProvisioningError("Sensor name must contain 1 to 120 characters.")
    if not 30 <= reporting_interval_seconds <= 86400:
        raise ProvisioningError("Reporting interval must be between 30 seconds and 24 hours.")
    key = issue_device_key()
    sensor = Sensor(
        id=str(uuid.uuid4()),
        home_id=home_id,
        room_id=room_id,
        name=name.strip(),
        key_hash=hash_device_key(key, pepper),
        status="active",
        reporting_interval_seconds=reporting_interval_seconds,
    )
    session.add(sensor)
    session.flush()
    return sensor, key


def rotate_sensor_key(session: Session, sensor: Sensor, pepper: str) -> str:
    if sensor.status != "active":
        raise ProvisioningError("Only active sensors can rotate a key.")
    key = issue_device_key()
    sensor.key_hash = hash_device_key(key, pepper)
    session.flush()
    return key


def revoke_sensor(sensor: Sensor) -> None:
    sensor.status = "revoked"