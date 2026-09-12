from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.access import is_walled, require_admin, require_matter_manage, require_matter_read
from app.audit import log_event
from app.db import get_db
from app.deps import get_current_user
from app.models import EthicalWall, Matter, MatterMember, Role, User
from app.schemas import MatterCreate, MatterOut, MemberIn, MemberOut, WallIn, WallOut
from app.seed import seed_if_needed

router = APIRouter(prefix="/matters", tags=["matters"])


@router.get("", response_model=list[MatterOut])
def list_matters(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> list[Matter]:
    matters = list(
        db.scalars(select(Matter).options(selectinload(Matter.members)).order_by(Matter.created_at.desc())).all()
    )
    visible = []
    for matter in matters:
        if is_walled(db, user.id, matter.id):
            continue
        if user.role == Role.ADMIN.value or any(member.user_id == user.id for member in matter.members):
            visible.append(matter)
    return visible


@router.post("", response_model=MatterOut, status_code=201)
def create_matter(payload: MatterCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> Matter:
    if user.role not in {Role.ADMIN.value, Role.ATTORNEY.value}:
        raise HTTPException(status_code=403, detail="Attorney or admin required")
    matter = Matter(**payload.model_dump(), created_by_id=user.id)
    db.add(matter)
    db.flush()
    db.add(MatterMember(matter_id=matter.id, user_id=user.id, member_role=user.role))
    log_event(db, action="matter.created", entity_type="matter", entity_id=matter.id, actor_id=user.id, matter_id=matter.id)
    db.commit()
    db.refresh(matter)
    return matter


@router.get("/{matter_id}", response_model=MatterOut)
def get_matter(matter_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> Matter:
    matter = db.get(Matter, matter_id)
    if matter is None:
        raise HTTPException(status_code=404, detail="Matter not found")
    require_matter_read(db, user, matter_id)
    return matter


@router.get("/{matter_id}/members", response_model=list[MemberOut])
def list_members(matter_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> list[MatterMember]:
    require_matter_read(db, user, matter_id)
    return list(
        db.scalars(
            select(MatterMember).options(selectinload(MatterMember.user)).where(MatterMember.matter_id == matter_id)
        ).all()
    )


@router.post("/{matter_id}/members", response_model=MemberOut, status_code=201)
def add_member(
    matter_id: str, payload: MemberIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> MatterMember:
    require_matter_manage(db, user, matter_id)
    member = MatterMember(matter_id=matter_id, user_id=payload.user_id, member_role=payload.member_role)
    db.add(member)
    db.flush()
    log_event(
        db,
        action="matter.member_added",
        entity_type="matter",
        entity_id=matter_id,
        actor_id=user.id,
        matter_id=matter_id,
        payload={"user_id": payload.user_id},
    )
    db.commit()
    db.refresh(member)
    return member


@router.get("/{matter_id}/walls", response_model=list[WallOut])
def list_walls(matter_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> list[EthicalWall]:
    require_matter_manage(db, user, matter_id)
    return list(db.scalars(select(EthicalWall).where(EthicalWall.matter_id == matter_id)).all())


@router.post("/{matter_id}/walls", response_model=WallOut, status_code=201)
def add_wall(
    matter_id: str, payload: WallIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> EthicalWall:
    require_admin(user)
    wall = EthicalWall(matter_id=matter_id, user_id=payload.user_id, reason=payload.reason)
    db.add(wall)
    db.flush()
    log_event(
        db,
        action="matter.wall_added",
        entity_type="ethical_wall",
        entity_id=wall.id,
        actor_id=user.id,
        matter_id=matter_id,
        payload={"user_id": payload.user_id},
    )
    db.commit()
    db.refresh(wall)
    return wall


@router.post("/demo/load")
def load_demo(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict:
    require_admin(user)
    seed_if_needed(db)
    matter = db.scalar(select(Matter).where(Matter.name.contains("Northwind")))
    log_event(db, action="demo.loaded", entity_type="matter", entity_id=matter.id if matter else "", actor_id=user.id)
    db.commit()
    return {"ok": True, "matter_id": matter.id if matter else None}
