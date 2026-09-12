from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.access import require_matter_read, require_matter_write
from app.audit import log_event
from app.db import get_db
from app.deps import get_current_user
from app.jobs import enqueue, run_job
from app.models import Cell, CellStatus, Document, Matter, ReviewTable, TableColumn, TableRow, User
from app.schemas import (
    ColumnIn,
    ColumnOut,
    HotItem,
    RowOut,
    RunIn,
    TableCreate,
    TableDetail,
    TableOut,
)
from app.seed import default_column_specs

router = APIRouter(tags=["tables"])


@router.get("/matters/{matter_id}/tables", response_model=list[TableOut])
def list_tables(matter_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> list[ReviewTable]:
    require_matter_read(db, user, matter_id)
    return list(
        db.scalars(
            select(ReviewTable)
            .options(selectinload(ReviewTable.columns))
            .where(ReviewTable.matter_id == matter_id)
        ).all()
    )


@router.post("/matters/{matter_id}/tables", response_model=TableOut, status_code=201)
def create_table(
    matter_id: str, payload: TableCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> ReviewTable:
    require_matter_write(db, user, matter_id)
    if db.get(Matter, matter_id) is None:
        raise HTTPException(status_code=404, detail="Matter not found")
    table = ReviewTable(
        matter_id=matter_id,
        name=payload.name,
        description=payload.description,
        created_by_id=user.id,
    )
    db.add(table)
    db.flush()
    specs = [c.model_dump() for c in payload.columns] if payload.columns else default_column_specs()
    for spec in specs:
        db.add(TableColumn(table_id=table.id, **spec))
    db.flush()
    if payload.include_all_documents:
        documents = db.scalars(select(Document).where(Document.matter_id == matter_id)).all()
        for document in documents:
            row = TableRow(table_id=table.id, document_id=document.id)
            db.add(row)
            db.flush()
            for column in table.columns:
                db.add(Cell(row_id=row.id, column_id=column.id))
    log_event(
        db,
        action="table.created",
        entity_type="review_table",
        entity_id=table.id,
        actor_id=user.id,
        matter_id=matter_id,
    )
    db.commit()
    db.refresh(table)
    return table


@router.get("/tables/{table_id}", response_model=TableDetail)
def get_table(table_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> ReviewTable:
    table = _load_table(db, table_id)
    require_matter_read(db, user, table.matter_id)
    return table


@router.post("/tables/{table_id}/columns", response_model=ColumnOut, status_code=201)
def add_column(
    table_id: str, payload: ColumnIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> TableColumn:
    table = db.get(ReviewTable, table_id)
    if table is None:
        raise HTTPException(status_code=404, detail="Table not found")
    require_matter_write(db, user, table.matter_id)
    column = TableColumn(table_id=table.id, **payload.model_dump())
    db.add(column)
    db.flush()
    for row in table.rows:
        db.add(Cell(row_id=row.id, column_id=column.id))
    log_event(db, action="column.created", entity_type="column", entity_id=column.id, actor_id=user.id, matter_id=table.matter_id)
    db.commit()
    db.refresh(column)
    return column


@router.post("/tables/{table_id}/run")
def run_table(
    table_id: str, payload: RunIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> dict:
    table = _load_table(db, table_id)
    require_matter_write(db, user, table.matter_id)
    queued = 0
    for row in table.rows:
        if payload.row_ids and row.id not in payload.row_ids:
            continue
        for cell in row.cells:
            if payload.column_ids and cell.column_id not in payload.column_ids:
                continue
            if cell.verified and not payload.include_verified:
                continue
            cell.status = CellStatus.QUEUED.value
            queued += 1
    db.commit()
    job = {
        "kind": "run_table",
        "table_id": table_id,
        "include_verified": payload.include_verified,
        "row_ids": payload.row_ids,
        "column_ids": payload.column_ids,
        "actor_id": user.id,
    }
    enqueue("run_table", job)
    log_event(
        db,
        action="table.run.queued",
        entity_type="review_table",
        entity_id=table_id,
        actor_id=user.id,
        matter_id=table.matter_id,
        payload={"queued": queued, "include_verified": payload.include_verified},
    )
    db.commit()
    return {"queued": queued}


@router.post("/tables/{table_id}/run-sync")
def run_table_sync(
    table_id: str, payload: RunIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> dict:
    """Used by tests and local demo when Redis is unavailable."""
    table = db.get(ReviewTable, table_id)
    if table is None:
        raise HTTPException(status_code=404, detail="Table not found")
    require_matter_write(db, user, table.matter_id)
    run_job(
        {
            "kind": "run_table",
            "table_id": table_id,
            "include_verified": payload.include_verified,
            "row_ids": payload.row_ids,
            "column_ids": payload.column_ids,
            "actor_id": user.id,
        }
    )
    return {"ok": True}


@router.post("/rows/{row_id}/hot", response_model=RowOut)
def toggle_hot(row_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> TableRow:
    row = db.get(TableRow, row_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Row not found")
    require_matter_write(db, user, row.table.matter_id)
    row.is_hot = not row.is_hot
    log_event(
        db,
        action="row.hot_toggled",
        entity_type="row",
        entity_id=row.id,
        actor_id=user.id,
        matter_id=row.table.matter_id,
        payload={"is_hot": row.is_hot},
    )
    db.commit()
    db.refresh(row)
    return row


@router.get("/matters/{matter_id}/hot", response_model=list[HotItem])
def hot_queue(matter_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> list[HotItem]:
    require_matter_read(db, user, matter_id)
    rows = db.scalars(
        select(TableRow)
        .join(ReviewTable)
        .options(selectinload(TableRow.document), selectinload(TableRow.cells), selectinload(TableRow.table))
        .where(ReviewTable.matter_id == matter_id)
    ).all()
    items: list[HotItem] = []
    for row in rows:
        flagged = sum(1 for cell in row.cells if cell.flagged)
        if row.is_hot or flagged:
            items.append(
                HotItem(
                    row_id=row.id,
                    document_id=row.document_id,
                    filename=row.document.filename if row.document else "",
                    flagged_cells=flagged,
                    is_hot=row.is_hot,
                    table_id=row.table_id,
                    table_name=row.table.name if row.table else "",
                )
            )
    return items


def _load_table(db: Session, table_id: str) -> ReviewTable:
    table = db.scalar(
        select(ReviewTable)
        .options(
            selectinload(ReviewTable.columns),
            selectinload(ReviewTable.rows).selectinload(TableRow.document),
            selectinload(ReviewTable.rows).selectinload(TableRow.cells).selectinload(Cell.comments),
        )
        .where(ReviewTable.id == table_id)
    )
    if table is None:
        raise HTTPException(status_code=404, detail="Table not found")
    return table
