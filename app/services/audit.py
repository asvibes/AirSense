import json
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.audit import AuditLog


def record_event(
    session: Session,
    *,
    home_id: str,
    actor_user_id: str | None,
    event_type: str,
    entity_type: str,
    entity_id: str | None = None,
    details: dict | None = None,
) -> AuditLog:
    event = AuditLog(
        home_id=home_id,
        actor_user_id=actor_user_id,
        event_type=event_type,
        entity_type=entity_type,
        entity_id=entity_id,
        details_json=json.dumps(details or {}, separators=(",", ":"), sort_keys=True),
        created_at=datetime.now(timezone.utc),
    )
    session.add(event)
    return event


def list_events(session: Session, home_id: str, *, limit: int = 100) -> list[dict]:
    rows = session.scalars(
        select(AuditLog)
        .where(AuditLog.home_id == home_id)
        .order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
        .limit(max(1, min(limit, 500)))
    )
    return [
        {
            "id": event.id,
            "actor_user_id": event.actor_user_id,
            "event_type": event.event_type,
            "entity_type": event.entity_type,
            "entity_id": event.entity_id,
            "details": json.loads(event.details_json),
            "created_at": event.created_at.isoformat(),
        }
        for event in rows
    ]