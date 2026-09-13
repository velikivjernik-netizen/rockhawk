from __future__ import annotations

import hashlib
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit import log_event
from app.config import get_settings
from app.ingest import extract_pages
from app.models import Cell, Document, DocumentPage, Matter, ReviewTable, TableRow, User
from app.seed import _toy_embedding
from app.storage import save_bytes

ALLOWED_SUFFIXES = {".pdf", ".docx", ".txt", ".md"}
ALLOWED_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "text/plain",
    "text/markdown",
    "application/octet-stream",
    "",
}


class UploadError(Exception):
    def __init__(self, message: str, status_code: int = 400, code: str = "error") -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.code = code


def content_sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def safe_relative_name(filename: str) -> str:
    cleaned = filename.replace("\\", "/")
    parts = [part for part in cleaned.split("/") if part not in {"", ".", ".."}]
    return "/".join(parts) or "upload.bin"


def validate_upload(filename: str, content_type: str | None, data: bytes) -> None:
    settings = get_settings()
    if not data:
        raise UploadError("Empty file")
    if len(data) > settings.max_upload_bytes:
        meg = settings.max_upload_bytes // (1024 * 1024)
        raise UploadError(f"File exceeds the {meg} MB size limit")
    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        raise UploadError("Unsupported file type. Use PDF, DOCX, or TXT.")
    ctype = (content_type or "").split(";")[0].strip().lower()
    if ctype not in ALLOWED_TYPES:
        raise UploadError(f"Unsupported media type: {content_type or 'unknown'}")


def find_duplicate(db: Session, matter_id: str, digest: str) -> Document | None:
    if not digest:
        return None
    return db.scalar(
        select(Document).where(Document.matter_id == matter_id, Document.content_hash == digest)
    )


def ingest_bytes(
    db: Session,
    *,
    matter: Matter,
    user: User,
    filename: str,
    content_type: str | None,
    data: bytes,
) -> Document:
    relative_name = safe_relative_name(filename)
    validate_upload(relative_name, content_type, data)
    digest = content_sha256(data)
    existing = find_duplicate(db, matter.id, digest)
    if existing is not None:
        raise UploadError(
            f"Duplicate of {existing.filename} (same content already on this matter)",
            status_code=409,
            code="duplicate",
        )
    try:
        pages = extract_pages(Path(relative_name).name or relative_name, data)
    except ValueError as exc:
        raise UploadError(str(exc)) from exc
    storage_name = relative_name
    if (Path(get_settings().storage_dir) / matter.id / storage_name).exists():
        stem = Path(relative_name).stem
        suffix = Path(relative_name).suffix
        parent = str(Path(relative_name).parent)
        uniqued = f"{stem}-{digest[:8]}{suffix}"
        storage_name = f"{parent}/{uniqued}" if parent not in {".", ""} else uniqued
    relative = f"{matter.id}/{storage_name}"
    save_bytes(relative, data)
    document = Document(
        matter_id=matter.id,
        filename=relative_name,
        content_type=content_type or "application/octet-stream",
        storage_path=relative,
        content_hash=digest,
        byte_size=len(data),
        page_count=len(pages),
        uploaded_by_id=user.id,
    )
    db.add(document)
    db.flush()
    for number, text in pages:
        db.add(
            DocumentPage(
                document_id=document.id,
                page_number=number,
                text=text,
                embedding=_toy_embedding(text),
            )
        )
    tables = list(db.scalars(select(ReviewTable).where(ReviewTable.matter_id == matter.id)).all())
    for table in tables:
        row = TableRow(table_id=table.id, document_id=document.id)
        db.add(row)
        db.flush()
        for column in table.columns:
            db.add(Cell(row_id=row.id, column_id=column.id))
    log_event(
        db,
        action="document.uploaded",
        entity_type="document",
        entity_id=document.id,
        actor_id=user.id,
        matter_id=matter.id,
        payload={"filename": relative_name, "pages": len(pages), "bytes": len(data), "sha256": digest},
    )
    return document
