from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.access import require_matter_read
from app.db import get_db
from app.deps import get_current_user
from app.models import AuditEvent, Role, User
from app.schemas import AuditOut

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("", response_model=list[AuditOut])
def list_audit(
    matter_id: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[AuditEvent]:
    if matter_id:
        require_matter_read(db, user, matter_id)
    elif user.role != Role.ADMIN.value:
        from fastapi import HTTPException

        raise HTTPException(status_code=403, detail="Admin required to view the global audit log")
    query = select(AuditEvent).order_by(AuditEvent.created_at.desc()).limit(500)
    if matter_id:
        query = query.where(AuditEvent.matter_id == matter_id)
    return list(db.scalars(query).all())
