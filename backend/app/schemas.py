from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    must_change_password: bool = False


class LoginIn(BaseModel):
    email: str
    password: str


class UserOut(ORMModel):
    id: str
    email: str
    name: str
    role: str
    is_active: bool
    must_change_password: bool
    admin_scopes: list[str] | None = None
    created_at: datetime


class UserCreate(BaseModel):
    email: str
    name: str
    password: str = Field(min_length=8)
    role: str = "reviewer"


class PasswordChange(BaseModel):
    current_password: str
    new_password: str = Field(min_length=10)


class MatterCreate(BaseModel):
    name: str
    description: str = ""
    client_name: str = ""
    opposing_party: str = ""


class MatterOut(ORMModel):
    id: str
    name: str
    description: str
    client_name: str
    opposing_party: str
    status: str
    created_at: datetime


class MemberIn(BaseModel):
    user_id: str
    member_role: str = "reviewer"


class MemberOut(ORMModel):
    id: str
    user_id: str
    member_role: str
    user: UserOut | None = None


class WallIn(BaseModel):
    user_id: str
    reason: str = "Ethical wall"


class WallOut(ORMModel):
    id: str
    user_id: str
    reason: str
    created_at: datetime


class PageOut(ORMModel):
    id: str
    page_number: int
    text: str


class DocumentOut(ORMModel):
    id: str
    matter_id: str
    filename: str
    content_type: str
    page_count: int
    status: str
    content_hash: str = ""
    byte_size: int = 0
    created_at: datetime


class BatchFileResult(BaseModel):
    filename: str
    status: str
    detail: str = ""
    document: DocumentOut | None = None


class BatchUploadOut(BaseModel):
    accepted: int
    failed: int
    duplicates: int
    results: list[BatchFileResult]


class ColumnIn(BaseModel):
    name: str
    value_type: str = "text"
    instruction: str = ""
    enum_options: list[str] | None = None
    condition_column_id: str | None = None
    condition_equals: str | None = None
    sort_order: int = 0
    citation_policy: str = "when_quoting"
    model_role: str = "extraction"
    prompt_key: str = "column.extract"
    prompt_version: str | None = None
    overwrite_policy: str = "skip_verified"
    required: bool = False
    validation_json: dict[str, Any] | None = None


class ColumnPatch(BaseModel):
    name: str | None = None
    value_type: str | None = None
    instruction: str | None = None
    enum_options: list[str] | None = None
    condition_column_id: str | None = None
    condition_equals: str | None = None
    sort_order: int | None = None
    citation_policy: str | None = None
    model_role: str | None = None
    prompt_key: str | None = None
    prompt_version: str | None = None
    overwrite_policy: str | None = None
    required: bool | None = None
    validation_json: dict[str, Any] | None = None


class ColumnOut(ORMModel):
    id: str
    name: str
    value_type: str
    instruction: str
    enum_options: list[str] | None
    condition_column_id: str | None
    condition_equals: str | None
    sort_order: int
    citation_policy: str = "when_quoting"
    model_role: str = "extraction"
    prompt_key: str = "column.extract"
    prompt_version: str | None = None
    overwrite_policy: str = "skip_verified"
    required: bool = False
    validation_json: dict[str, Any] | None = None


class ColumnSuggestIn(BaseModel):
    description: str = Field(min_length=3)


class ColumnBulkIn(BaseModel):
    columns: list[ColumnIn]


class TableCreate(BaseModel):
    name: str
    description: str = ""
    columns: list[ColumnIn] | None = None
    include_all_documents: bool = True


class TablePatch(BaseModel):
    name: str | None = None
    description: str | None = None
    hot_include_flagged: bool | None = None
    hot_include_manual: bool | None = None
    hot_min_flagged: int | None = None


class TableOut(ORMModel):
    id: str
    matter_id: str
    name: str
    description: str
    hot_include_flagged: bool = True
    hot_include_manual: bool = True
    hot_min_flagged: int = 1
    created_at: datetime
    columns: list[ColumnOut] = []


class CommentIn(BaseModel):
    body: str = Field(min_length=1)


class CommentOut(ORMModel):
    id: str
    cell_id: str
    user_id: str
    body: str
    created_at: datetime
    user: UserOut | None = None


class CellOut(ORMModel):
    id: str
    row_id: str
    column_id: str
    value: str
    status: str
    verified: bool
    flagged: bool
    assigned_to_id: str | None
    citations: list[Any]
    evidence_quote: str
    provider: str
    error_message: str
    updated_at: datetime
    comments: list[CommentOut] = []


class CellPatch(BaseModel):
    value: str | None = None
    verified: bool | None = None
    flagged: bool | None = None
    assigned_to_id: str | None = None


class RowOut(ORMModel):
    id: str
    table_id: str
    document_id: str
    is_hot: bool
    document: DocumentOut | None = None
    cells: list[CellOut] = []


class TableDetail(TableOut):
    rows: list[RowOut] = []


class RunIn(BaseModel):
    include_verified: bool = False
    row_ids: list[str] | None = None
    column_ids: list[str] | None = None


class AskIn(BaseModel):
    question: str = Field(min_length=3)
    thread_id: str | None = None


class AskMessageOut(ORMModel):
    id: str
    role: str
    body: str
    citations: list[Any]
    created_at: datetime


class AskOut(BaseModel):
    thread_id: str
    messages: list[AskMessageOut]


class AuditOut(ORMModel):
    id: str
    actor_id: str | None
    action: str
    entity_type: str
    entity_id: str
    matter_id: str | None
    payload: dict[str, Any]
    created_at: datetime


class HotItem(BaseModel):
    row_id: str
    document_id: str
    filename: str
    flagged_cells: int
    is_hot: bool
    table_id: str
    table_name: str


class AdminDraftIn(BaseModel):
    changes: dict[str, Any]
    expected_revision_id: str | None = None


class AdminApplyIn(BaseModel):
    reason: str = Field(min_length=8)
    confirm: bool = False
    expected_revision_id: str | None = None


class AdminRollbackIn(BaseModel):
    reason: str = Field(min_length=8)


class AdminApprovalIn(BaseModel):
    decision: str = "approved"


class AdminImportIn(BaseModel):
    bundle: dict[str, Any]
    dry_run: bool = True


class PromptVersionIn(BaseModel):
    prompt_key: str
    body: str = Field(min_length=8)
    note: str = ""
