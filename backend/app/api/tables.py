from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.access import require_matter_read, require_matter_write
from app.audit import log_event
from app.column_suggest import propose_from_tabular, suggest_from_text
from app.config_service import effective_bool, ensure_baseline, get_effective
from app.db import get_db
from app.deps import get_current_user
from app.jobs import enqueue, run_job
from app.models import Cell, CellStatus, Document, Matter, ReviewTable, TableColumn, TableRow, User
from app.schemas import (
    ColumnBulkIn,
    ColumnIn,
    ColumnOut,
    ColumnPatch,
    ColumnSuggestIn,
    HotItem,
    RowOut,
    RunIn,
    TableCreate,
    TableDetail,
    TableOut,
    TablePatch,
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
    specs = default_column_specs() if payload.columns is None else [c.model_dump() for c in payload.columns]
    for spec in specs:
        _validate_column_spec(spec)
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


@router.patch("/tables/{table_id}", response_model=TableOut)
def patch_table(
    table_id: str, payload: TablePatch, db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> ReviewTable:
    table = db.get(ReviewTable, table_id)
    if table is None:
        raise HTTPException(status_code=404, detail="Table not found")
    require_matter_write(db, user, table.matter_id)
    data = payload.model_dump(exclude_unset=True)
    for key, value in data.items():
        setattr(table, key, value)
    log_event(
        db,
        action="table.updated",
        entity_type="review_table",
        entity_id=table.id,
        actor_id=user.id,
        matter_id=table.matter_id,
        payload=data,
    )
    db.commit()
    db.refresh(table)
    return table


@router.post("/tables/{table_id}/columns", response_model=ColumnOut, status_code=201)
def add_column(
    table_id: str, payload: ColumnIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> TableColumn:
    table = db.get(ReviewTable, table_id)
    if table is None:
        raise HTTPException(status_code=404, detail="Table not found")
    require_matter_write(db, user, table.matter_id)
    spec = payload.model_dump()
    _validate_column_spec(spec)
    column = TableColumn(table_id=table.id, **spec)
    db.add(column)
    db.flush()
    for row in table.rows:
        db.add(Cell(row_id=row.id, column_id=column.id))
    log_event(db, action="column.created", entity_type="column", entity_id=column.id, actor_id=user.id, matter_id=table.matter_id)
    db.commit()
    db.refresh(column)
    return column


@router.post("/tables/{table_id}/columns/bulk", response_model=list[ColumnOut], status_code=201)
def add_columns_bulk(
    table_id: str, payload: ColumnBulkIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> list[TableColumn]:
    table = db.get(ReviewTable, table_id)
    if table is None:
        raise HTTPException(status_code=404, detail="Table not found")
    require_matter_write(db, user, table.matter_id)
    created: list[TableColumn] = []
    for item in payload.columns:
        spec = item.model_dump()
        _validate_column_spec(spec)
        column = TableColumn(table_id=table.id, **spec)
        db.add(column)
        db.flush()
        for row in table.rows:
            db.add(Cell(row_id=row.id, column_id=column.id))
        created.append(column)
        log_event(db, action="column.created", entity_type="column", entity_id=column.id, actor_id=user.id, matter_id=table.matter_id)
    db.commit()
    for column in created:
        db.refresh(column)
    return created


@router.post("/tables/{table_id}/columns/suggest")
def suggest_columns(
    table_id: str, payload: ColumnSuggestIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> dict:
    table = db.get(ReviewTable, table_id)
    if table is None:
        raise HTTPException(status_code=404, detail="Table not found")
    require_matter_write(db, user, table.matter_id)
    ensure_baseline(db, user.id)
    if not effective_bool(db, "feature.column_suggest"):
        raise HTTPException(status_code=403, detail="Column suggestions are disabled")
    citation = str(get_effective(db, "review.citation_required_default").value or "when_quoting")
    proposed = suggest_from_text(payload.description, citation_policy=citation)
    log_event(
        db,
        action="column.suggested",
        entity_type="review_table",
        entity_id=table.id,
        actor_id=user.id,
        matter_id=table.matter_id,
        payload={"count": len(proposed), "persisted": False},
    )
    db.commit()
    return {"proposed": proposed, "persisted": False}


@router.post("/tables/{table_id}/columns/import")
def import_columns(
    table_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    table = db.get(ReviewTable, table_id)
    if table is None:
        raise HTTPException(status_code=404, detail="Table not found")
    require_matter_write(db, user, table.matter_id)
    data = file.file.read()
    proposed = propose_from_tabular(file.filename or "checklist.csv", data)
    log_event(
        db,
        action="column.imported",
        entity_type="review_table",
        entity_id=table.id,
        actor_id=user.id,
        matter_id=table.matter_id,
        payload={"filename": file.filename, "count": len(proposed), "persisted": False},
    )
    db.commit()
    return {"proposed": proposed, "persisted": False, "filename": file.filename}


@router.patch("/columns/{column_id}", response_model=ColumnOut)
def patch_column(
    column_id: str, payload: ColumnPatch, db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> TableColumn:
    column = db.get(TableColumn, column_id)
    if column is None:
        raise HTTPException(status_code=404, detail="Column not found")
    require_matter_write(db, user, column.table.matter_id)
    data = payload.model_dump(exclude_unset=True)
    merged = {
        "name": data.get("name", column.name),
        "value_type": data.get("value_type", column.value_type),
        "enum_options": data.get("enum_options", column.enum_options),
    }
    _validate_column_spec(merged)
    for key, value in data.items():
        setattr(column, key, value)
    log_event(
        db,
        action="column.updated",
        entity_type="column",
        entity_id=column.id,
        actor_id=user.id,
        matter_id=column.table.matter_id,
        payload={"keys": sorted(data.keys())},
    )
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
    ensure_baseline(db, user.id)
    global_flagged = effective_bool(db, "review.hot.include_flagged")
    global_manual = effective_bool(db, "review.hot.include_manual")
    items: list[HotItem] = []
    for row in rows:
        flagged = sum(1 for cell in row.cells if cell.flagged)
        include_flagged = global_flagged and row.table.hot_include_flagged and flagged >= (row.table.hot_min_flagged or 1)
        include_manual = global_manual and row.table.hot_include_manual and row.is_hot
        if include_manual or include_flagged:
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


def _validate_column_spec(spec: dict) -> None:
    value_type = spec.get("value_type") or "text"
    if value_type not in {"text", "boolean", "date", "number", "money", "enum"}:
        raise HTTPException(status_code=400, detail=f"Unsupported column type: {value_type}")
    if value_type == "enum" and not spec.get("enum_options"):
        raise HTTPException(status_code=400, detail="Enum columns require enum_options")
    if spec.get("citation_policy") and spec["citation_policy"] not in {"always", "when_quoting", "optional", "never"}:
        raise HTTPException(status_code=400, detail="Invalid citation_policy")
    if spec.get("model_role") and spec["model_role"] not in {
        "orchestrator",
        "triage",
        "extraction",
        "qc",
        "synthesis",
        "embeddings",
    }:
        raise HTTPException(status_code=400, detail="Invalid model_role")
    if spec.get("overwrite_policy") and spec["overwrite_policy"] not in {
        "skip_verified",
        "overwrite_unverified",
        "overwrite_all",
    }:
        raise HTTPException(status_code=400, detail="Invalid overwrite_policy")


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
