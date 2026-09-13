"""document content hash and size

Revision ID: 002_document_hash
Revises: 001_initial
Create Date: 2026-09-13
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "002_document_hash"
down_revision: Union[str, None] = "001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("documents", sa.Column("content_hash", sa.String(64), nullable=False, server_default=""))
    op.add_column("documents", sa.Column("byte_size", sa.Integer(), nullable=False, server_default="0"))
    op.create_index("ix_documents_content_hash", "documents", ["content_hash"])


def downgrade() -> None:
    op.drop_index("ix_documents_content_hash", table_name="documents")
    op.drop_column("documents", "byte_size")
    op.drop_column("documents", "content_hash")
