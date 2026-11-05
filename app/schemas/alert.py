from datetime import datetime

from app.timestamps import format_utc


def reading_json(
    *, room_id: str, metric: str, value: float, measured_at: datetime, unit: str
) -> dict:
    return {
        "room_id": room_id,
        "metric": metric,
        "value": value,
        "unit": unit,
        "measured_at": format_utc(measured_at),
    }