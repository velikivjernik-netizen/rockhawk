from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def new_id() -> str:
    return str(uuid.uuid4())


class Role(str, Enum):
    ADMIN = "admin"
    ATTORNEY = "attorney"
    REVIEWER = "reviewer"
    VIEWER = "viewer"


class ColumnType(str, Enum):
    TEXT = "text"
    BOOLEAN = "boolean"
    DATE = "date"
    NUMBER = "number"
    MONEY = "money"
    ENUM = "enum"


class CellStatus(str, Enum):
    IDLE = "idle"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETE = "complete"
    NOT_FOUND = "not_found"
    ERROR = "error"


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    hashed_password: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(32), default=Role.REVIEWER.value)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=False)
    admin_scopes: Mapped[list | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    memberships: Mapped[list[MatterMember]] = relationship(back_populates="user")


class Matter(Base):
    __tablename__ = "matters"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text, default="")
    client_name: Mapped[str] = mapped_column(String(255), default="")
    opposing_party: Mapped[str] = mapped_column(String(255), default="")
    status: Mapped[str] = mapped_column(String(32), default="open")
    created_by_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    members: Mapped[list[MatterMember]] = relationship(back_populates="matter", cascade="all, delete-orphan")
    documents: Mapped[list[Document]] = relationship(back_populates="matter", cascade="all, delete-orphan")
    tables: Mapped[list[ReviewTable]] = relationship(back_populates="matter", cascade="all, delete-orphan")
    walls: Mapped[list[EthicalWall]] = relationship(back_populates="matter", cascade="all, delete-orphan")


class MatterMember(Base):
    __tablename__ = "matter_members"
    __table_args__ = (UniqueConstraint("matter_id", "user_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    matter_id: Mapped[str] = mapped_column(ForeignKey("matters.id", ondelete="CASCADE"))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    member_role: Mapped[str] = mapped_column(String(32), default=Role.REVIEWER.value)

    matter: Mapped[Matter] = relationship(back_populates="members")
    user: Mapped[User] = relationship(back_populates="memberships")


class EthicalWall(Base):
    __tablename__ = "ethical_walls"
    __table_args__ = (UniqueConstraint("matter_id", "user_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    matter_id: Mapped[str] = mapped_column(ForeignKey("matters.id", ondelete="CASCADE"))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    reason: Mapped[str] = mapped_column(Text, default="Ethical wall")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    matter: Mapped[Matter] = relationship(back_populates="walls")
    user: Mapped[User] = relationship()


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    matter_id: Mapped[str] = mapped_column(ForeignKey("matters.id", ondelete="CASCADE"), index=True)
    filename: Mapped[str] = mapped_column(String(512))
    content_type: Mapped[str] = mapped_column(String(128), default="application/octet-stream")
    storage_path: Mapped[str] = mapped_column(String(1024))
    content_hash: Mapped[str] = mapped_column(String(64), default="", index=True)
    byte_size: Mapped[int] = mapped_column(Integer, default=0)
    page_count: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(32), default="ready")
    uploaded_by_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    matter: Mapped[Matter] = relationship(back_populates="documents")
    pages: Mapped[list[DocumentPage]] = relationship(back_populates="document", cascade="all, delete-orphan")
    rows: Mapped[list[TableRow]] = relationship(back_populates="document")


class DocumentPage(Base):
    __tablename__ = "document_pages"
    __table_args__ = (UniqueConstraint("document_id", "page_number"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), index=True)
    page_number: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text, default="")
    embedding: Mapped[list | None] = mapped_column(JSON, nullable=True)

    document: Mapped[Document] = relationship(back_populates="pages")


class ReviewTable(Base):
    __tablename__ = "review_tables"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    matter_id: Mapped[str] = mapped_column(ForeignKey("matters.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text, default="")
    hot_include_flagged: Mapped[bool] = mapped_column(Boolean, default=True)
    hot_include_manual: Mapped[bool] = mapped_column(Boolean, default=True)
    hot_min_flagged: Mapped[int] = mapped_column(Integer, default=1)
    created_by_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    matter: Mapped[Matter] = relationship(back_populates="tables")
    columns: Mapped[list[TableColumn]] = relationship(
        back_populates="table", cascade="all, delete-orphan", order_by="TableColumn.sort_order"
    )
    rows: Mapped[list[TableRow]] = relationship(back_populates="table", cascade="all, delete-orphan")


class TableColumn(Base):
    __tablename__ = "table_columns"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    table_id: Mapped[str] = mapped_column(ForeignKey("review_tables.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    value_type: Mapped[str] = mapped_column(String(32), default=ColumnType.TEXT.value)
    instruction: Mapped[str] = mapped_column(Text, default="")
    enum_options: Mapped[list | None] = mapped_column(JSON, nullable=True)
    condition_column_id: Mapped[str | None] = mapped_column(ForeignKey("table_columns.id"), nullable=True)
    condition_equals: Mapped[str | None] = mapped_column(String(255), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    citation_policy: Mapped[str] = mapped_column(String(32), default="when_quoting")
    model_role: Mapped[str] = mapped_column(String(32), default="extraction")
    prompt_key: Mapped[str] = mapped_column(String(128), default="column.extract")
    prompt_version: Mapped[str | None] = mapped_column(String(32), nullable=True)
    overwrite_policy: Mapped[str] = mapped_column(String(32), default="skip_verified")
    required: Mapped[bool] = mapped_column(Boolean, default=False)
    validation_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    table: Mapped[ReviewTable] = relationship(back_populates="columns")
    condition_column: Mapped[TableColumn | None] = relationship(remote_side="TableColumn.id")
    cells: Mapped[list[Cell]] = relationship(back_populates="column")


class TableRow(Base):
    __tablename__ = "table_rows"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    table_id: Mapped[str] = mapped_column(ForeignKey("review_tables.id", ondelete="CASCADE"), index=True)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"))
    is_hot: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    table: Mapped[ReviewTable] = relationship(back_populates="rows")
    document: Mapped[Document] = relationship(back_populates="rows")
    cells: Mapped[list[Cell]] = relationship(back_populates="row", cascade="all, delete-orphan")


class Cell(Base):
    __tablename__ = "cells"
    __table_args__ = (UniqueConstraint("row_id", "column_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    row_id: Mapped[str] = mapped_column(ForeignKey("table_rows.id", ondelete="CASCADE"), index=True)
    column_id: Mapped[str] = mapped_column(ForeignKey("table_columns.id", ondelete="CASCADE"), index=True)
    value: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(32), default=CellStatus.IDLE.value)
    verified: Mapped[bool] = mapped_column(Boolean, default=False)
    flagged: Mapped[bool] = mapped_column(Boolean, default=False)
    assigned_to_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    citations: Mapped[list] = mapped_column(JSON, default=list)
    evidence_quote: Mapped[str] = mapped_column(Text, default="")
    provider: Mapped[str] = mapped_column(String(64), default="")
    error_message: Mapped[str] = mapped_column(Text, default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    row: Mapped[TableRow] = relationship(back_populates="cells")
    column: Mapped[TableColumn] = relationship(back_populates="cells")
    assigned_to: Mapped[User | None] = relationship()
    comments: Mapped[list[CellComment]] = relationship(back_populates="cell", cascade="all, delete-orphan")


class CellComment(Base):
    __tablename__ = "cell_comments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    cell_id: Mapped[str] = mapped_column(ForeignKey("cells.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    body: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    cell: Mapped[Cell] = relationship(back_populates="comments")
    user: Mapped[User] = relationship()


class AskThread(Base):
    __tablename__ = "ask_threads"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    table_id: Mapped[str] = mapped_column(ForeignKey("review_tables.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    title: Mapped[str] = mapped_column(String(255), default="Ask RockHawk")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    messages: Mapped[list[AskMessage]] = relationship(back_populates="thread", cascade="all, delete-orphan")


class AskMessage(Base):
    __tablename__ = "ask_messages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    thread_id: Mapped[str] = mapped_column(ForeignKey("ask_threads.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(16))
    body: Mapped[str] = mapped_column(Text)
    citations: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    thread: Mapped[AskThread] = relationship(back_populates="messages")


class AuditEvent(Base):
    """Append-only. Application code must never UPDATE or DELETE rows."""

    __tablename__ = "audit_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    actor_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    action: Mapped[str] = mapped_column(String(64), index=True)
    entity_type: Mapped[str] = mapped_column(String(64))
    entity_id: Mapped[str] = mapped_column(String(36), default="")
    matter_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ConfigurationRevision(Base):
    __tablename__ = "configuration_revisions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    number: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(32), default="applied")
    parent_id: Mapped[str | None] = mapped_column(ForeignKey("configuration_revisions.id"), nullable=True)
    created_by_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    reason: Mapped[str] = mapped_column(Text, default="")
    note: Mapped[str] = mapped_column(Text, default="")

    values: Mapped[list[ConfigurationValue]] = relationship(back_populates="revision", cascade="all, delete-orphan")


class ConfigurationValue(Base):
    __tablename__ = "configuration_values"
    __table_args__ = (UniqueConstraint("revision_id", "key"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    revision_id: Mapped[str] = mapped_column(ForeignKey("configuration_revisions.id", ondelete="CASCADE"), index=True)
    key: Mapped[str] = mapped_column(String(128), index=True)
    value_json: Mapped[dict | list | str | int | float | bool | None] = mapped_column(JSON, nullable=True)

    revision: Mapped[ConfigurationRevision] = relationship(back_populates="values")


class ConfigurationPointer(Base):
    """Singleton active-revision pointer (id='global')."""

    __tablename__ = "configuration_pointers"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default="global")
    active_revision_id: Mapped[str | None] = mapped_column(ForeignKey("configuration_revisions.id"), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class ConfigurationDraft(Base):
    __tablename__ = "configuration_drafts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    created_by_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    status: Mapped[str] = mapped_column(String(32), default="open")
    proposed_json: Mapped[dict] = mapped_column(JSON, default=dict)
    validation_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    preview_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    expected_revision_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    confirm_phrase: Mapped[str] = mapped_column(String(64), default="")


class ConfigurationChangeRequest(Base):
    __tablename__ = "configuration_change_requests"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    draft_id: Mapped[str] = mapped_column(ForeignKey("configuration_drafts.id", ondelete="CASCADE"), index=True)
    requested_by_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="pending")
    reason: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ConfigurationApproval(Base):
    __tablename__ = "configuration_approvals"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    draft_id: Mapped[str] = mapped_column(ForeignKey("configuration_drafts.id", ondelete="CASCADE"), index=True)
    approver_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    decision: Mapped[str] = mapped_column(String(16), default="approved")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ConfigurationApplyEvent(Base):
    __tablename__ = "configuration_apply_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    revision_id: Mapped[str | None] = mapped_column(ForeignKey("configuration_revisions.id"), nullable=True)
    draft_id: Mapped[str | None] = mapped_column(ForeignKey("configuration_drafts.id"), nullable=True)
    actor_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(32))
    detail_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class SecretReference(Base):
    __tablename__ = "secret_references"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(128))
    ciphertext: Mapped[str] = mapped_column(Text, default="")
    hint: Mapped[str] = mapped_column(String(16), default="••••")
    created_by_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class FeatureFlag(Base):
    __tablename__ = "feature_flags"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    key: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    description: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class PromptVersion(Base):
    __tablename__ = "prompt_versions"
    __table_args__ = (UniqueConstraint("prompt_key", "version"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    prompt_key: Mapped[str] = mapped_column(String(128), index=True)
    version: Mapped[str] = mapped_column(String(32))
    body: Mapped[str] = mapped_column(Text)
    note: Mapped[str] = mapped_column(Text, default="")
    parent_version: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created_by_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
