from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.access import require_matter_read
from app.audit import log_event
from app.db import get_db
from app.deps import get_current_user
from app.jobs import run_job
from app.models import AskMessage, AskThread, ReviewTable, User
from app.schemas import AskIn, AskMessageOut, AskOut

router = APIRouter(tags=["ask"])


@router.post("/tables/{table_id}/ask", response_model=AskOut)
def ask(
    table_id: str, payload: AskIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> AskOut:
    table = db.get(ReviewTable, table_id)
    if table is None:
        raise HTTPException(status_code=404, detail="Table not found")
    require_matter_read(db, user, table.matter_id)
    thread = db.get(AskThread, payload.thread_id) if payload.thread_id else None
    if thread is None:
        thread = AskThread(table_id=table_id, user_id=user.id, title=payload.question[:80])
        db.add(thread)
        db.flush()
    db.add(AskMessage(thread_id=thread.id, role="user", body=payload.question, citations=[]))
    db.commit()
    run_job({"kind": "ask", "thread_id": thread.id, "question": payload.question, "actor_id": user.id})
    messages = list(
        db.scalars(select(AskMessage).where(AskMessage.thread_id == thread.id).order_by(AskMessage.created_at)).all()
    )
    log_event(
        db,
        action="ask.asked",
        entity_type="ask_thread",
        entity_id=thread.id,
        actor_id=user.id,
        matter_id=table.matter_id,
    )
    db.commit()
    return AskOut(thread_id=thread.id, messages=[AskMessageOut.model_validate(m) for m in messages])


@router.get("/ask/{thread_id}", response_model=AskOut)
def get_thread(thread_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> AskOut:
    thread = db.get(AskThread, thread_id)
    if thread is None:
        raise HTTPException(status_code=404, detail="Thread not found")
    table = db.get(ReviewTable, thread.table_id)
    require_matter_read(db, user, table.matter_id)
    messages = list(
        db.scalars(select(AskMessage).where(AskMessage.thread_id == thread.id).order_by(AskMessage.created_at)).all()
    )
    return AskOut(thread_id=thread.id, messages=[AskMessageOut.model_validate(m) for m in messages])
