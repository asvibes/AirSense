from flask import Blueprint, current_app, jsonify, request
from sqlalchemy import select

from app.db import get_session
from app.models.metric import Metric
from app.models.sensor import Sensor
from app.security.device_keys import verify_device_key
from app.services.ingestion.ingest import ingest_reading
from app.services.ingestion.rejections import record_rejection
from app.services.ingestion.validate import ReadingValidationError, validate_reading


sensor_readings = Blueprint("sensor_readings", __name__)


@sensor_readings.post("/api/sensors/<sensor_id>/readings")
def ingest_sensor_reading(sensor_id: str):
    limiter = current_app.extensions["airsense_rate_limiter"]
    if not limiter.allow(
        f"device:{sensor_id}:{request.remote_addr or 'unknown'}",
        limit=120,
        window_seconds=60,
    ):
        return jsonify(error="Reading rate limit exceeded."), 429
    db = get_session()
    sensor = db.scalar(select(Sensor).where(Sensor.id == sensor_id))
    supplied = request.headers.get("X-Device-Key", "")
    pepper = current_app.config.get("DEVICE_KEY_PEPPER") or current_app.config["SECRET_KEY"]
    if (
        sensor is None
        or sensor.status != "active"
        or not supplied
        or not verify_device_key(supplied, sensor.key_hash, pepper)
    ):
        return jsonify(error="A valid active sensor key is required."), 401
    payload = request.get_json(silent=True)
    try:
        reading = validate_reading(payload)
        if reading["room"] != sensor.room.name:
            raise ReadingValidationError("Reading room does not match the provisioned sensor room.")
        metric = db.get(Metric, reading["metric"])
        if metric is not None and metric.unit != reading["unit"]:
            raise ReadingValidationError(
                f"Metric {metric.code} uses {metric.unit}, not {reading['unit']}."
            )
        result = ingest_reading(
            db,
            home_id=sensor.home_id,
            home_name="",
            payload=payload,
            source="device",
            defaults=_policy_defaults(),
            max_future_seconds=current_app.config["MAX_FUTURE_SECONDS"],
            actor_user_id=None,
            sensor_id=sensor.id,
        )
    except (ReadingValidationError, ValueError) as error:
        record_rejection(
            db,
            home_id=sensor.home_id,
            sensor_id=sensor.id,
            reason=str(error),
        )
        db.commit()
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