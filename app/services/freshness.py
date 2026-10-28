from datetime import datetime, timezone

from app.models.sensor import Sensor


def sensor_freshness(sensor: Sensor, now: datetime | None = None) -> dict:
    current = now or datetime.now(timezone.utc)
    last_seen = sensor.last_seen_at
    if last_seen is not None and last_seen.tzinfo is None:
        last_seen = last_seen.replace(tzinfo=timezone.utc)
    age = (current - last_seen).total_seconds() if last_seen else None
    if sensor.status != "active":
        state = "inactive"
    elif age is None:
        state = "never_seen"
    elif age > sensor.reporting_interval_seconds * 2:
        state = "stale"
    else:
        state = "fresh"
    return {
        "state": state,
        "last_seen_at": last_seen.isoformat() if last_seen else None,
        "age_seconds": max(0, int(age)) if age is not None else None,
        "reporting_interval_seconds": sensor.reporting_interval_seconds,
    }