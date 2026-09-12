from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, selectinload

from app.access import require_matter_read, require_matter_write
from app.audit import log_event
from app.db import get_db
from app.deps import get_current_user
from app.models import Cell, CellComment, User
from app.schemas import CellOut, CellPatch, CommentIn, CommentOut

router = APIRouter(tags=["cells"])


@router.get("/cells/{cell_id}", response_model=CellOut)
def get_cell(cell_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> Cell:
    cell = _cell(db, cell_id)
    require_matter_read(db, user, cell.row.table.matter_id)
    return cell


@router.patch("/cells/{cell_id}", response_model=CellOut)
def patch_cell(
    cell_id: str, payload: CellPatch, db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> Cell:
    cell = _cell(db, cell_id)
    require_matter_write(db, user, cell.row.table.matter_id)
    before = {"value": cell.value, "verified": cell.verified, "flagged": cell.flagged, "assigned_to_id": cell.assigned_to_id}
    data = payload.model_dump(exclude_unset=True)
    for key, value in data.items():
        setattr(cell, key, value)
    log_event(
        db,
        action="cell.updated",
        entity_type="cell",
        entity_id=cell.id,
        actor_id=user.id,
        matter_id=cell.row.table.matter_id,
        payload={"before": before, "after": data},
    )
    db.commit()
    db.refresh(cell)
    return cell


@router.post("/cells/{cell_id}/comments", response_model=CommentOut, status_code=201)
def add_comment(
    cell_id: str, payload: CommentIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> CellComment:
    cell = _cell(db, cell_id)
    require_matter_write(db, user, cell.row.table.matter_id)
    comment = CellComment(cell_id=cell.id, user_id=user.id, body=payload.body)
    db.add(comment)
    db.flush()
    log_event(
        db,
        action="cell.commented",
        entity_type="cell",
        entity_id=cell.id,
        actor_id=user.id,
        matter_id=cell.row.table.matter_id,
    )
    db.commit()
    db.refresh(comment)
    return comment


def _cell(db: Session, cell_id: str) -> Cell:
    from app.models import TableRow

    cell = db.get(Cell, cell_id)
    if cell is None:
        raise HTTPException(status_code=404, detail="Cell not found")
    db.refresh(cell)
    _ = cell.row.table
    _ = cell.comments
    return cell
