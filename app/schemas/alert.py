from datetime import datetime


def reading_json(
    *, room_id: str, metric: str, value: float, measured_at: datetime, unit: str
) -> dict:
    return {
        "room_id": room_id,
        "metric": metric,
        "value": value,
        "unit": unit,
        "measured_at": measured_at.isoformat(),
    }