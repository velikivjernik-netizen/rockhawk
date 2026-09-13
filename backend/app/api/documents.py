from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.access import require_matter_read, require_matter_write
from app.db import get_db
from app.deps import get_current_user
from app.documents import UploadError, ingest_bytes
from app.models import Document, DocumentPage, Matter, User
from app.schemas import BatchFileResult, BatchUploadOut, DocumentOut, PageOut
from app.storage import read_bytes

router = APIRouter(tags=["documents"])


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
    matter = db.get(Matter, matter_id)
    if matter is None:
        raise HTTPException(status_code=404, detail="Matter not found")
    data = await file.read()
    try:
        document = ingest_bytes(
            db,
            matter=matter,
            user=user,
            filename=file.filename or "upload.bin",
            content_type=file.content_type,
            data=data,
        )
    except UploadError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    db.commit()
    db.refresh(document)
    return document


@router.post("/matters/{matter_id}/documents/batch", response_model=BatchUploadOut)
async def upload_documents_batch(
    matter_id: str,
    files: list[UploadFile] = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> BatchUploadOut:
    require_matter_write(db, user, matter_id)
    matter = db.get(Matter, matter_id)
    if matter is None:
        raise HTTPException(status_code=404, detail="Matter not found")
    if not files:
        raise HTTPException(status_code=400, detail="No files in the batch")

    results: list[BatchFileResult] = []
    accepted = failed = duplicates = 0
    for upload in files:
        filename = upload.filename or "upload.bin"
        data = await upload.read()
        try:
            document = ingest_bytes(
                db,
                matter=matter,
                user=user,
                filename=filename,
                content_type=upload.content_type,
                data=data,
            )
            db.commit()
            db.refresh(document)
            accepted += 1
            results.append(
                BatchFileResult(filename=filename, status="created", document=DocumentOut.model_validate(document))
            )
        except UploadError as exc:
            db.rollback()
            matter = db.get(Matter, matter_id)
            if exc.code == "duplicate":
                duplicates += 1
                status = "duplicate"
            else:
                failed += 1
                status = "error"
            results.append(BatchFileResult(filename=filename, status=status, detail=exc.message))
        except Exception as exc:  # noqa: BLE001
            db.rollback()
            matter = db.get(Matter, matter_id)
            failed += 1
            results.append(BatchFileResult(filename=filename, status="error", detail=str(exc)))
    return BatchUploadOut(accepted=accepted, failed=failed, duplicates=duplicates, results=results)


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
