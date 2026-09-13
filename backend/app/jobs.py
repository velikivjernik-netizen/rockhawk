from __future__ import annotations

import json
import threading
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.factory import get_provider
from app.audit import log_event
from app.config import get_settings
from app.config_service import effective_bool, ensure_baseline
from app.db import SessionLocal
from app.models import (
    AskMessage,
    AskThread,
    Cell,
    CellStatus,
    DocumentPage,
    ReviewTable,
    TableColumn,
    TableRow,
)

JOB_QUEUE = "rockhawk:jobs"


def _redis():
    url = get_settings().redis_url
    if not url:
        return None
    try:
        import redis

        client = redis.Redis.from_url(url)
        client.ping()
        return client
    except Exception:
        return None


def enqueue(kind: str, payload: dict[str, Any]) -> None:
    body = json.dumps({"kind": kind, **payload})
    client = _redis()
    if client is not None:
        client.rpush(JOB_QUEUE, body)
        return
    thread = threading.Thread(target=run_job, args=(json.loads(body),), daemon=True)
    thread.start()


def run_job(job: dict[str, Any]) -> None:
    kind = job.get("kind")
    db = SessionLocal()
    try:
        if kind == "run_table":
            _run_table(db, job)
        elif kind == "ask":
            _run_ask(db, job)
    finally:
        db.close()


def process_one_from_redis() -> bool:
    client = _redis()
    if client is None:
        return False
    item = client.lpop(JOB_QUEUE)
    if not item:
        return False
    run_job(json.loads(item))
    return True


def _run_table(db: Session, job: dict[str, Any]) -> None:
    table = db.get(ReviewTable, job["table_id"])
    if table is None:
        return
    include_verified = bool(job.get("include_verified"))
    ensure_baseline(db)
    preserve_verified = effective_bool(db, "review.preserve_verified_cells")
    row_filter = set(job.get("row_ids") or [])
    col_filter = set(job.get("column_ids") or [])
    rows = list(table.rows)
    columns = list(table.columns)
    if row_filter:
        rows = [row for row in rows if row.id in row_filter]
    if col_filter:
        columns = [col for col in columns if col.id in col_filter]

    for row in rows:
        cells_by_col = {cell.column_id: cell for cell in row.cells}
        for column in sorted(columns, key=lambda c: c.sort_order):
            cell = cells_by_col.get(column.id)
            if cell is None:
                continue
            if cell.verified and preserve_verified and not include_verified:
                continue
            if cell.verified and getattr(column, "overwrite_policy", "skip_verified") != "overwrite_all" and not include_verified:
                continue
            if not _condition_met(column, cells_by_col):
                cell.status = CellStatus.NOT_FOUND.value
                cell.value = "Not found"
                cell.citations = []
                cell.evidence_quote = "Conditional column skipped: prerequisite not met."
                cell.provider = get_provider(db, role=getattr(column, "model_role", None) or "extraction").name
                continue
            _extract_cell(db, cell, column, row)

    log_event(
        db,
        action="table.run.completed",
        entity_type="review_table",
        entity_id=table.id,
        actor_id=job.get("actor_id"),
        matter_id=table.matter_id,
        payload={"include_verified": include_verified},
    )
    db.commit()


def _condition_met(column: TableColumn, cells_by_col: dict[str, Cell]) -> bool:
    if not column.condition_column_id:
        return True
    source = cells_by_col.get(column.condition_column_id)
    if source is None:
        return False
    expected = (column.condition_equals or "true").strip().lower()
    actual = (source.value or "").strip().lower()
    if expected in {"true", "yes", "1"}:
        return actual in {"true", "yes", "1"}
    return actual == expected


def _extract_cell(db: Session, cell: Cell, column: TableColumn, row: TableRow) -> None:
    cell.status = CellStatus.RUNNING.value
    db.flush()
    pages = db.scalars(
        select(DocumentPage).where(DocumentPage.document_id == row.document_id).order_by(DocumentPage.page_number)
    ).all()
            provider = get_provider(db, role=getattr(column, "model_role", None) or "extraction")
            result = provider.extract(
        column_name=column.name,
        value_type=column.value_type,
        instruction=column.instruction,
        enum_options=column.enum_options,
        pages=[(p.page_number, p.text) for p in pages],
        document_id=row.document_id,
        document_name=row.document.filename if row.document else "",
    )
    cell.value = result.value
    cell.evidence_quote = result.evidence_quote
    cell.provider = result.provider
    cell.citations = [
        {
            "document_id": c.document_id,
            "document_name": c.document_name,
            "page": c.page,
            "quote": c.quote,
        }
        for c in result.citations
    ]
    cell.error_message = ""
    cell.status = CellStatus.NOT_FOUND.value if result.not_found else CellStatus.COMPLETE.value


def _run_ask(db: Session, job: dict[str, Any]) -> None:
    thread = db.get(AskThread, job["thread_id"])
    if thread is None:
        return
    table = db.get(ReviewTable, thread.table_id)
    if table is None:
        return
    question = job["question"]
    snippets = _grounding_snippets(table, question)
    result = get_provider(db, role="synthesis").answer(question=question, snippets=snippets)
    db.add(
        AskMessage(
            thread_id=thread.id,
            role="assistant",
            body=result.value,
            citations=[
                {
                    "document_id": c.document_id,
                    "document_name": c.document_name,
                    "page": c.page,
                    "quote": c.quote,
                }
                for c in result.citations
            ],
        )
    )
    log_event(
        db,
        action="ask.answered",
        entity_type="ask_thread",
        entity_id=thread.id,
        actor_id=job.get("actor_id"),
        matter_id=table.matter_id,
        payload={"not_found": result.not_found},
    )
    db.commit()


def _grounding_snippets(table: ReviewTable, question: str) -> list[dict]:
    terms = {t for t in question.lower().split() if len(t) > 3}
    snippets: list[dict] = []
    for row in table.rows:
        filename = row.document.filename if row.document else ""
        for cell in row.cells:
            blob = f"{cell.column.name if cell.column else ''} {cell.value}".lower()
            score = sum(1 for t in terms if t in blob) if terms else 1
            if score:
                snippets.append(
                    {
                        "label": f"{filename} / {cell.column.name if cell.column else 'cell'}",
                        "text": cell.value,
                        "cell_id": cell.id,
                        "column": cell.column.name if cell.column else "",
                        "document_id": row.document_id,
                        "document_name": filename,
                        "page": (cell.citations or [{}])[0].get("page") if cell.citations else None,
                        "score": score,
                    }
                )
        if row.document:
            for page in row.document.pages:
                score = sum(1 for t in terms if t in page.text.lower()) if terms else 0
                if score:
                    snippets.append(
                        {
                            "label": f"{filename} p.{page.page_number}",
                            "text": page.text[:500],
                            "document_id": row.document_id,
                            "document_name": filename,
                            "page": page.page_number,
                            "score": score,
                        }
                    )
    snippets.sort(key=lambda item: item.get("score", 0), reverse=True)
    return snippets[:16]
