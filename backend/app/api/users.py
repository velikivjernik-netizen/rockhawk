from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.access import require_admin
from app.audit import log_event
from app.db import get_db
from app.deps import get_current_user
from app.models import Role, User
from app.schemas import UserCreate, UserOut
from app.security import hash_password

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=list[UserOut])
def list_users(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> list[User]:
    require_admin(user)
    return list(db.scalars(select(User).order_by(User.email)).all())


@router.post("", response_model=UserOut, status_code=201)
def create_user(payload: UserCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> User:
    require_admin(user)
    if payload.role not in {item.value for item in Role}:
        raise HTTPException(status_code=400, detail="Unknown role")
    if db.scalar(select(User).where(User.email == payload.email.lower())):
        raise HTTPException(status_code=409, detail="Email already exists")
    created = User(
        email=payload.email.lower(),
        name=payload.name,
        hashed_password=hash_password(payload.password),
        role=payload.role,
        must_change_password=True,
    )
    db.add(created)
    db.flush()
    log_event(db, action="user.created", entity_type="user", entity_id=created.id, actor_id=user.id)
    db.commit()
    db.refresh(created)
    return created
