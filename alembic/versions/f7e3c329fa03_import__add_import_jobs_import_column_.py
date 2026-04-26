"""import_: add import_jobs import_column_mappings import_row_errors import_outbox

Revision ID: f7e3c329fa03
Revises: 7c1e29c7372f
Create Date: 2026-04-26 01:01:06.208642

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID


revision: str = 'f7e3c329fa03'
down_revision: Union[str, None] = '7c1e29c7372f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # import_jobs
    op.create_table(
        "import_jobs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("user_id", UUID(as_uuid=True), nullable=False),
        sa.Column("file_path", sa.Text, nullable=False),
        sa.Column("original_filename", sa.Text, nullable=True),
        sa.Column("source_type", sa.String(30), nullable=False),
        sa.Column("temporal_workflow_id", sa.Text, nullable=True),
        sa.Column("status", sa.String(30), nullable=False, server_default="uploaded"),
        sa.Column("total_rows", sa.Integer, nullable=True),
        sa.Column("imported_rows", sa.Integer, nullable=False, server_default="0"),
        sa.Column("skipped_rows", sa.Integer, nullable=False, server_default="0"),
        sa.Column("failed_rows", sa.Integer, nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "source_type IN ('csv_generic','xlsx_generic','splitwise_csv')",
            name="ck_import_jobs_source_type",
        ),
        sa.CheckConstraint(
            "status IN ('uploaded','awaiting_mapping','processing','completed','failed')",
            name="ck_import_jobs_status",
        ),
    )
    op.create_index("ix_import_jobs_user_id", "import_jobs", ["user_id"])

    # import_column_mappings
    op.create_table(
        "import_column_mappings",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "job_id",
            UUID(as_uuid=True),
            sa.ForeignKey("import_jobs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("source_column", sa.Text, nullable=False),
        sa.Column("mapped_to", sa.String(30), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "mapped_to IN ('date','description','debit_amount','credit_amount','amount','balance','category','ignore')",
            name="ck_import_column_mappings_mapped_to",
        ),
    )
    op.create_index("ix_import_column_mappings_job_id", "import_column_mappings", ["job_id"])

    # import_row_errors
    op.create_table(
        "import_row_errors",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "job_id",
            UUID(as_uuid=True),
            sa.ForeignKey("import_jobs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("row_index", sa.Integer, nullable=False),
        sa.Column("reason", sa.Text, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_import_row_errors_job_id", "import_row_errors", ["job_id"])

    # import_outbox
    op.create_table(
        "import_outbox",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column("payload", JSONB, nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attempt_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("last_error", sa.String(1000), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_import_outbox_event_type", "import_outbox", ["event_type"])
    op.create_index("ix_import_outbox_status", "import_outbox", ["status"])


def downgrade() -> None:
    op.drop_table("import_outbox")
    op.drop_table("import_row_errors")
    op.drop_table("import_column_mappings")
    op.drop_table("import_jobs")
