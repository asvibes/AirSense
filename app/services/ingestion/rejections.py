from app.services.audit import record_event


def record_rejection(
    session,
    *,
    home_id: str | None,
    sensor_id: str | None,
    source: str,
    actor_user_id: str | None = None,
) -> None:
    if not home_id:
        return
    record_event(
        session,
        home_id=home_id,
        actor_user_id=actor_user_id,
        event_type="reading.rejected",
        entity_type="sensor" if sensor_id else "reading",
        entity_id=sensor_id,
        details={"reason": "invalid_reading", "source": source},
    )