from datetime import datetime, timezone

from app.models.audit import AuditLog


def record_rejection(
    session,
    *,
    home_id: str | None,
    sensor_id: str | None,
    reason: str,
) -> None:
    if not home_id:
        return
    session.add(
        AuditLog(
            home_id=home_id,
            actor_user_id=None,
            event_type="reading.rejected",
            entity_type="sensor",
            entity_id=sensor_id,
            details_json='{"reason":' + _json_string(reason[:160]) + "}",
            created_at=datetime.now(timezone.utc),
        )
    )


def _json_string(value: str) -> str:
    import json

    return json.dumps(value)