import math
import re
from datetime import datetime, timezone


class ReadingValidationError(ValueError):
    pass


def validate_reading(payload: object) -> dict:
    if not isinstance(payload, dict):
        raise ReadingValidationError("Reading body must be a JSON object.")
    room = payload.get("room")
    metric = payload.get("metric", "CO2")
    unit = payload.get("unit", "ppm")
    value = payload.get("value", payload.get("co2_ppm"))
    if not isinstance(room, str) or not room.strip() or len(room.strip()) > 100:
        raise ReadingValidationError("room must contain 1 to 100 characters.")
    if not isinstance(metric, str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{0,31}", metric):
        raise ReadingValidationError("metric must be a valid metric code.")
    if not isinstance(unit, str) or not re.fullmatch(r"[A-Za-z0-9/%._-]{1,24}", unit):
        raise ReadingValidationError("unit must contain 1 to 24 valid characters.")
    if isinstance(value, bool):
        raise ReadingValidationError("value must be a finite non-negative number.")
    try:
        number = float(value)
    except (TypeError, ValueError) as error:
        raise ReadingValidationError("value must be a finite non-negative number.") from error
    if not math.isfinite(number) or number < 0:
        raise ReadingValidationError("value must be a finite non-negative number.")
    measured_at = payload.get("measured_at")
    if measured_at is None:
        parsed = datetime.now(timezone.utc)
    elif isinstance(measured_at, str):
        try:
            parsed = datetime.fromisoformat(measured_at.replace("Z", "+00:00"))
        except ValueError as error:
            raise ReadingValidationError("measured_at must be an ISO-8601 timestamp.") from error
        if parsed.tzinfo is None:
            raise ReadingValidationError("measured_at must include a timezone.")
        parsed = parsed.astimezone(timezone.utc)
    else:
        raise ReadingValidationError("measured_at must be an ISO-8601 timestamp.")
    return {
        "room": room.strip(),
        "metric": metric.upper(),
        "unit": unit,
        "value": number,
        "measured_at": parsed,
    }