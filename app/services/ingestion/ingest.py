from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.repositories.alerts import process_reading
from app.services.audit import record_event
from app.services.ingestion.validate import validate_reading


def ingest_reading(
    session: Session,
    *,
    home_id: str,
    home_name: str,
    payload: object,
    source: str,
    defaults: dict,
    max_future_seconds: int,
    actor_user_id: str | None,
    sensor_id: str | None = None,
) -> dict:
    reading = validate_reading(payload)
    result = process_reading(
        session,
        home_id=home_id,
        home_name=home_name,
        room_name=reading["room"],
        metric_code=reading["metric"],
        unit=reading["unit"],
        value=reading["value"],
        source=source,
        measured_at=reading["measured_at"],
        defaults=defaults,
        max_future_seconds=max_future_seconds,
        sensor_id=sensor_id,
    )
    if sensor_id:
        from app.models.sensor import Sensor

        sensor = session.get(Sensor, sensor_id)
        if sensor:
            sensor.last_seen_at = datetime.now(timezone.utc)
    record_event(
        session,
        home_id=home_id,
        actor_user_id=actor_user_id,
        event_type="reading.ingested",
        entity_type="reading",
        entity_id=str(result["reading_id"]),
        details={"source": source, "metric": reading["metric"]},
    )
    session.commit()
    return result