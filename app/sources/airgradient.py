from datetime import datetime, timezone
from numbers import Real


class AirGradientPayloadError(ValueError):
    pass


def is_airgradient_payload(payload: object) -> bool:
    return isinstance(payload, dict) and "rco2" in payload


def normalize_airgradient_payload(
    payload: object,
    *,
    room_name: str,
) -> dict[str, object]:
    if not isinstance(payload, dict):
        raise AirGradientPayloadError("AirGradient payload must be a JSON object.")
    if not room_name.strip() or len(room_name) > 100:
        raise AirGradientPayloadError("The provisioned sensor room is invalid.")

    supplied_room = payload.get("room")
    if supplied_room is not None and supplied_room != room_name:
        raise AirGradientPayloadError(
            "Reading room does not match the provisioned sensor room."
        )
    if "rco2" not in payload:
        raise AirGradientPayloadError("AirGradient payload must include rco2.")

    reading: dict[str, object] = {
        "room": room_name,
        "metric": "CO2",
        "unit": "ppm",
        "value": payload["rco2"],
    }
    timestamp = payload.get("measured_at", payload.get("timestamp", payload.get("ts")))
    if timestamp is not None:
        if isinstance(timestamp, bool):
            raise AirGradientPayloadError("AirGradient timestamp is invalid.")
        if isinstance(timestamp, Real):
            timestamp_value = float(timestamp)
            if timestamp_value > 1e12:
                timestamp_value /= 1000
            try:
                timestamp = datetime.fromtimestamp(
                    timestamp_value, tz=timezone.utc
                ).isoformat()
            except (OverflowError, OSError, ValueError) as error:
                raise AirGradientPayloadError(
                    "AirGradient timestamp is invalid."
                ) from error
        if not isinstance(timestamp, str):
            raise AirGradientPayloadError("AirGradient timestamp is invalid.")
        reading["measured_at"] = timestamp
    return reading