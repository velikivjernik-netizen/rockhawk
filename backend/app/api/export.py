import csv
import io

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from openpyxl import Workbook
from sqlalchemy.orm import Session, selectinload

from app.access import require_matter_read
from app.audit import log_event
from app.db import get_db
from app.deps import get_current_user
from app.models import ReviewTable, TableRow, User

router = APIRouter(tags=["export"])


@router.get("/tables/{table_id}/export.csv")
def export_csv(table_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> StreamingResponse:
    table = _table(db, table_id)
    require_matter_read(db, user, table.matter_id)
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    headers = ["Document", *[col.name for col in table.columns], "Hot"]
    writer.writerow(headers)
    for row in table.rows:
        cells = {cell.column_id: cell for cell in row.cells}
        writer.writerow(
            [
                row.document.filename if row.document else "",
                *[cells.get(col.id).value if cells.get(col.id) else "" for col in table.columns],
                "yes" if row.is_hot else "",
            ]
        )
    log_event(db, action="table.exported", entity_type="review_table", entity_id=table.id, actor_id=user.id, matter_id=table.matter_id, payload={"format": "csv"})
    db.commit()
    buffer.seek(0)
    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{table.name}.csv"'},
    )


@router.get("/tables/{table_id}/export.xlsx")
def export_xlsx(table_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> StreamingResponse:
    table = _table(db, table_id)
    require_matter_read(db, user, table.matter_id)
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Review"
    sheet.append(["Document", *[col.name for col in table.columns], "Hot", "Verified flags"])
    for row in table.rows:
        cells = {cell.column_id: cell for cell in row.cells}
        verified = ",".join(col.name for col in table.columns if cells.get(col.id) and cells[col.id].verified)
        sheet.append(
            [
                row.document.filename if row.document else "",
                *[cells.get(col.id).value if cells.get(col.id) else "" for col in table.columns],
                "yes" if row.is_hot else "",
                verified,
            ]
        )
    buffer = io.BytesIO()
    workbook.save(buffer)
    buffer.seek(0)
    log_event(db, action="table.exported", entity_type="review_table", entity_id=table.id, actor_id=user.id, matter_id=table.matter_id, payload={"format": "xlsx"})
    db.commit()
    return StreamingResponse(
        buffer,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{table.name}.xlsx"'},
    )


def _table(db: Session, table_id: str) -> ReviewTable:
    table = db.scalar(
        select_table(table_id)
    )
    if table is None:
        raise HTTPException(status_code=404, detail="Table not found")
    return table


def select_table(table_id: str):
    from sqlalchemy import select

    return (
        select(ReviewTable)
        .options(
            selectinload(ReviewTable.columns),
            selectinload(ReviewTable.rows).selectinload(TableRow.document),
            selectinload(ReviewTable.rows).selectinload(TableRow.cells),
        )
        .where(ReviewTable.id == table_id)
    )
