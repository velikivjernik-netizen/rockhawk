from fastapi import APIRouter, Depends, HTTPException, UploadFile
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.access import require_matter_read, require_matter_write
from app.audit import log_event
from app.db import get_db
from app.deps import get_current_user
from app.ingest import extract_pages
from app.models import Document, DocumentPage, Matter, TableRow, User
from app.schemas import DocumentOut, PageOut
from app.seed import _toy_embedding
from app.storage import read_bytes, save_bytes

router = APIRouter(tags=["documents"])

ALLOWED = {
    "application/pdf": ".pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
    "text/plain": ".txt",
}


@router.get("/matters/{matter_id}/documents", response_model=list[DocumentOut])
def list_documents(matter_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> list[Document]:
    require_matter_read(db, user, matter_id)
    return list(db.scalars(select(Document).where(Document.matter_id == matter_id).order_by(Document.created_at)).all())


@router.post("/matters/{matter_id}/documents", response_model=DocumentOut, status_code=201)
async def upload_document(
    matter_id: str,
    file: UploadFile,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Document:
    require_matter_write(db, user, matter_id)
    if db.get(Matter, matter_id) is None:
        raise HTTPException(status_code=404, detail="Matter not found")
    data = await file.read()
    filename = file.filename or "upload.bin"
    try:
        pages = extract_pages(filename, data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    relative = f"{matter_id}/{filename}"
    save_bytes(relative, data)
    document = Document(
        matter_id=matter_id,
        filename=filename,
        content_type=file.content_type or "application/octet-stream",
        storage_path=relative,
        page_count=len(pages),
        uploaded_by_id=user.id,
    )
    db.add(document)
    db.flush()
    for number, text in pages:
        db.add(DocumentPage(document_id=document.id, page_number=number, text=text, embedding=_toy_embedding(text)))
    for table in db.get(Matter, matter_id).tables:
        row = TableRow(table_id=table.id, document_id=document.id)
        db.add(row)
        db.flush()
        for column in table.columns:
            from app.models import Cell

            db.add(Cell(row_id=row.id, column_id=column.id))
    log_event(
        db,
        action="document.uploaded",
        entity_type="document",
        entity_id=document.id,
        actor_id=user.id,
        matter_id=matter_id,
        payload={"filename": filename, "pages": len(pages)},
    )
    db.commit()
    db.refresh(document)
    return document


@router.get("/documents/{document_id}", response_model=DocumentOut)
def get_document(document_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> Document:
    document = db.get(Document, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")
    require_matter_read(db, user, document.matter_id)
    return document


@router.get("/documents/{document_id}/pages", response_model=list[PageOut])
def get_pages(document_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> list[DocumentPage]:
    document = db.get(Document, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")
    require_matter_read(db, user, document.matter_id)
    return list(
        db.scalars(
            select(DocumentPage).where(DocumentPage.document_id == document_id).order_by(DocumentPage.page_number)
        ).all()
    )


@router.get("/documents/{document_id}/file")
def download_file(document_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> Response:
    document = db.get(Document, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")
    require_matter_read(db, user, document.matter_id)
    return Response(
        content=read_bytes(document.storage_path),
        media_type=document.content_type,
        headers={"Content-Disposition": f'inline; filename="{document.filename}"'},
    )
