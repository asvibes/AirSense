import math
import re
from datetime import datetime, timezone

from app.parameters import canonical_metric_code, normalize_value, parameter_for_code, parse_unit


class ReadingValidationError(ValueError):
    pass


def validate_reading(payload: object) -> dict:
    if not isinstance(payload, dict):
        raise ReadingValidationError("Reading body must be a JSON object.")
    room = payload.get("room")
    metric = payload.get("metric", "CO2")
    value = payload.get("value", payload.get("co2_ppm"))
    if not isinstance(room, str) or not room.strip() or len(room.strip()) > 100:
        raise ReadingValidationError("room must contain 1 to 100 characters.")
    if not isinstance(metric, str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_.-]{0,31}", metric):
        raise ReadingValidationError("metric must be a valid metric code.")
    if isinstance(value, bool):
        raise ReadingValidationError("value must be a finite non-negative number.")
    try:
        number = float(value)
    except (TypeError, ValueError) as error:
        raise ReadingValidationError("value must be a finite non-negative number.") from error
    if not math.isfinite(number):
        raise ReadingValidationError("value must be a finite non-negative number.")
    canonical_metric = canonical_metric_code(metric)
    parameter = parameter_for_code(canonical_metric)
    unit = payload.get("unit")
    if unit is None:
        if parameter:
            unit = parameter.unit
        elif canonical_metric == "CO2":
            unit = "ppm"
        else:
            raise ReadingValidationError("unit is required for unrecognized metrics.")
    if not isinstance(unit, str) or not re.fullmatch(r"[A-Za-z0-9/%._µμ°³²-]{1,24}", unit):
        raise ReadingValidationError("unit must contain 1 to 24 valid characters.")
    if parameter:
        normalized_unit = parse_unit(unit)
        try:
            number, unit, _assumed = normalize_value(number, parameter, normalized_unit)
        except ValueError as error:
            raise ReadingValidationError(str(error)) from error
    elif number < 0:
        raise ReadingValidationError("value must be a finite non-negative number.")
    metric_name = parameter.name if parameter else payload.get("metric_name", canonical_metric)
    if not isinstance(metric_name, str) or not metric_name.strip() or len(metric_name.strip()) > 80:
        raise ReadingValidationError("metric_name must contain 1 to 80 characters.")
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
        "metric": canonical_metric,
        "metric_name": metric_name.strip(),
        "unit": unit,
        "value": number,
        "measured_at": parsed,
    }