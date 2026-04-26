"""statements: add statement_uploads extraction_jobs raw_extracted_rows raw_row_items statements_outbox

Revision ID: 69d337c9fb49
Revises: e1ee25db7b49
Create Date: 2026-04-25 17:12:40.407957

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = '69d337c9fb49'
down_revision: Union[str, None] = 'e1ee25db7b49'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── statement_uploads ──────────────────────────────────────────────────────
    op.create_table(
        "statement_uploads",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("account_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("account_kind", sa.String(20), nullable=False),
        sa.Column("file_path", sa.Text, nullable=False),
        sa.Column("file_type", sa.String(10), nullable=False),
        sa.Column("original_filename", sa.Text, nullable=True),
        sa.Column("period_start", sa.Date, nullable=True),
        sa.Column("period_end", sa.Date, nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="uploaded"),
        sa.Column(
            "uploaded_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "account_kind IN ('bank','credit_card')",
            name="ck_statement_uploads_account_kind",
        ),
        sa.CheckConstraint(
            "file_type IN ('pdf','csv')",
            name="ck_statement_uploads_file_type",
        ),
        sa.CheckConstraint(
            "status IN ('uploaded','processing','completed','partial','failed')",
            name="ck_statement_uploads_status",
        ),
    )

    # ── extraction_jobs ────────────────────────────────────────────────────────
    op.create_table(
        "extraction_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "upload_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("statement_uploads.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("temporal_workflow_id", sa.Text, nullable=True),
        sa.Column("status", sa.String(30), nullable=False, server_default="queued"),
        sa.Column("total_rows", sa.Integer, nullable=True),
        sa.Column("classified_rows", sa.Integer, nullable=False, server_default="0"),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('queued','parsing','classifying','awaiting_input','completed','partial','failed')",
            name="ck_extraction_jobs_status",
        ),
    )

    # ── raw_extracted_rows ─────────────────────────────────────────────────────
    op.create_table(
        "raw_extracted_rows",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "job_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("extraction_jobs.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("row_index", sa.Integer, nullable=False),
        sa.Column("date", sa.Date, nullable=True),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("debit_amount", sa.Numeric(15, 2), nullable=True),
        sa.Column("credit_amount", sa.Numeric(15, 2), nullable=True),
        sa.Column("balance", sa.Numeric(15, 2), nullable=True),
        sa.Column(
            "classification_status",
            sa.String(30),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("ai_suggested_category_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("ai_confidence", sa.Float, nullable=True),
        sa.Column("final_category_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("transaction_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "classification_status IN ('pending','auto_classified','user_classified','skipped')",
            name="ck_raw_extracted_rows_classification_status",
        ),
    )

    # ── raw_row_items ──────────────────────────────────────────────────────────
    op.create_table(
        "raw_row_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "row_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("raw_extracted_rows.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("label", sa.Text, nullable=True),
        sa.Column("amount", sa.Numeric(15, 2), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    # ── statements_outbox ──────────────────────────────────────────────────────
    op.create_table(
        "statements_outbox",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("event_type", sa.String(100), nullable=False, index=True),
        sa.Column("payload", postgresql.JSONB, nullable=False),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="pending",
            index=True,
        ),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attempt_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("last_error", sa.String(1000), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_table("statements_outbox")
    op.drop_table("raw_row_items")
    op.drop_table("raw_extracted_rows")
    op.drop_table("extraction_jobs")
    op.drop_table("statement_uploads")
