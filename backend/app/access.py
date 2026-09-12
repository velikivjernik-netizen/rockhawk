from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import EthicalWall, MatterMember, Role, User

WRITE_ROLES = {Role.ADMIN.value, Role.ATTORNEY.value, Role.REVIEWER.value}
MANAGE_ROLES = {Role.ADMIN.value, Role.ATTORNEY.value}


def is_walled(db: Session, user_id: str, matter_id: str) -> bool:
    wall = db.scalar(
        select(EthicalWall).where(EthicalWall.user_id == user_id, EthicalWall.matter_id == matter_id)
    )
    return wall is not None


def is_member(db: Session, user_id: str, matter_id: str) -> bool:
    member = db.scalar(
        select(MatterMember).where(MatterMember.user_id == user_id, MatterMember.matter_id == matter_id)
    )
    return member is not None


def require_matter_read(db: Session, user: User, matter_id: str) -> None:
    if is_walled(db, user.id, matter_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Ethical wall blocks this matter")
    if user.role == Role.ADMIN.value:
        return
    if not is_member(db, user.id, matter_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not assigned to this matter")


def require_matter_write(db: Session, user: User, matter_id: str) -> None:
    require_matter_read(db, user, matter_id)
    if user.role not in WRITE_ROLES and user.role != Role.ADMIN.value:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Read-only role")


def require_matter_manage(db: Session, user: User, matter_id: str) -> None:
    require_matter_read(db, user, matter_id)
    if user.role not in MANAGE_ROLES:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Attorney or admin required")


def require_admin(user: User) -> None:
    if user.role != Role.ADMIN.value:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin required")
