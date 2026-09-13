"""admin configuration core and column builder fields

Revision ID: 003_admin_and_columns
Revises: 002_document_hash
Create Date: 2026-09-13
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "003_admin_and_columns"
down_revision: Union[str, None] = "002_document_hash"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("admin_scopes", sa.JSON(), nullable=True))
    op.add_column("review_tables", sa.Column("hot_include_flagged", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.add_column("review_tables", sa.Column("hot_include_manual", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.add_column("review_tables", sa.Column("hot_min_flagged", sa.Integer(), nullable=False, server_default="1"))
    op.add_column("table_columns", sa.Column("citation_policy", sa.String(32), nullable=False, server_default="when_quoting"))
    op.add_column("table_columns", sa.Column("model_role", sa.String(32), nullable=False, server_default="extraction"))
    op.add_column("table_columns", sa.Column("prompt_key", sa.String(128), nullable=False, server_default="column.extract"))
    op.add_column("table_columns", sa.Column("prompt_version", sa.String(32), nullable=True))
    op.add_column("table_columns", sa.Column("overwrite_policy", sa.String(32), nullable=False, server_default="skip_verified"))
    op.add_column("table_columns", sa.Column("required", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("table_columns", sa.Column("validation_json", sa.JSON(), nullable=True))

    op.create_table(
        "configuration_revisions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("parent_id", sa.String(36), sa.ForeignKey("configuration_revisions.id"), nullable=True),
        sa.Column("created_by_id", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("note", sa.Text(), nullable=False),
    )
    op.create_table(
        "configuration_values",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("revision_id", sa.String(36), sa.ForeignKey("configuration_revisions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("key", sa.String(128), nullable=False),
        sa.Column("value_json", sa.JSON(), nullable=True),
        sa.UniqueConstraint("revision_id", "key"),
    )
    op.create_index("ix_configuration_values_revision_id", "configuration_values", ["revision_id"])
    op.create_index("ix_configuration_values_key", "configuration_values", ["key"])
    op.create_table(
        "configuration_pointers",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("active_revision_id", sa.String(36), sa.ForeignKey("configuration_revisions.id"), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "configuration_drafts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("created_by_id", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("proposed_json", sa.JSON(), nullable=False),
        sa.Column("validation_json", sa.JSON(), nullable=True),
        sa.Column("preview_json", sa.JSON(), nullable=True),
        sa.Column("expected_revision_id", sa.String(36), nullable=True),
        sa.Column("confirm_phrase", sa.String(64), nullable=False),
    )
    op.create_table(
        "configuration_change_requests",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("draft_id", sa.String(36), sa.ForeignKey("configuration_drafts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("requested_by_id", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "configuration_approvals",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("draft_id", sa.String(36), sa.ForeignKey("configuration_drafts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("approver_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("decision", sa.String(16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "configuration_apply_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("revision_id", sa.String(36), sa.ForeignKey("configuration_revisions.id"), nullable=True),
        sa.Column("draft_id", sa.String(36), sa.ForeignKey("configuration_drafts.id"), nullable=True),
        sa.Column("actor_id", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("detail_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "secret_references",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("ciphertext", sa.Text(), nullable=False),
        sa.Column("hint", sa.String(16), nullable=False),
        sa.Column("created_by_id", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "feature_flags",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("key", sa.String(128), nullable=False, unique=True),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "prompt_versions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("prompt_key", sa.String(128), nullable=False),
        sa.Column("version", sa.String(32), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("note", sa.Text(), nullable=False),
        sa.Column("parent_version", sa.String(32), nullable=True),
        sa.Column("created_by_id", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("prompt_key", "version"),
    )


def downgrade() -> None:
    op.drop_table("prompt_versions")
    op.drop_table("feature_flags")
    op.drop_table("secret_references")
    op.drop_table("configuration_apply_events")
    op.drop_table("configuration_approvals")
    op.drop_table("configuration_change_requests")
    op.drop_table("configuration_drafts")
    op.drop_table("configuration_pointers")
    op.drop_index("ix_configuration_values_key", table_name="configuration_values")
    op.drop_index("ix_configuration_values_revision_id", table_name="configuration_values")
    op.drop_table("configuration_values")
    op.drop_table("configuration_revisions")
    op.drop_column("table_columns", "validation_json")
    op.drop_column("table_columns", "required")
    op.drop_column("table_columns", "overwrite_policy")
    op.drop_column("table_columns", "prompt_version")
    op.drop_column("table_columns", "prompt_key")
    op.drop_column("table_columns", "model_role")
    op.drop_column("table_columns", "citation_policy")
    op.drop_column("review_tables", "hot_min_flagged")
    op.drop_column("review_tables", "hot_include_manual")
    op.drop_column("review_tables", "hot_include_flagged")
    op.drop_column("users", "admin_scopes")
