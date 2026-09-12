from typing import Any

from sqlalchemy.orm import Session

from app.models import AuditEvent


def log_event(
    db: Session,
    *,
    action: str,
    entity_type: str,
    entity_id: str = "",
    actor_id: str | None = None,
    matter_id: str | None = None,
    payload: dict[str, Any] | None = None,
) -> AuditEvent:
    event = AuditEvent(
        actor_id=actor_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        matter_id=matter_id,
        payload=payload or {},
    )
    db.add(event)
    db.flush()
    return event
