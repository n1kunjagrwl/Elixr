"""earnings: add earning_sources earnings earnings_outbox

Revision ID: a707f5ee953b
Revises: f7e3c329fa03
Create Date: 2026-04-26 01:10:10.085579

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 'a707f5ee953b'
down_revision: Union[str, None] = 'f7e3c329fa03'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_SOURCE_TYPE_CHECK = (
    "type IN ('salary','freelance','rental','dividend','interest','business','other')"
)
_EARNING_SOURCE_TYPE_CHECK = (
    "source_type IN ('salary','freelance','rental','dividend','interest','business','other')"
)


def upgrade() -> None:
    # ── earning_sources ───────────────────────────────────────────────────────
    op.create_table(
        "earning_sources",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("type", sa.String(30), nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(_SOURCE_TYPE_CHECK, name="ck_earning_sources_type"),
    )
    op.create_index("ix_earning_sources_user_id", "earning_sources", ["user_id"])

    # ── earnings ──────────────────────────────────────────────────────────────
    op.create_table(
        "earnings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("transaction_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("source_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("source_type", sa.String(30), nullable=False),
        sa.Column("source_label", sa.Text, nullable=True),
        sa.Column("amount", sa.Numeric(15, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="INR"),
        sa.Column("date", sa.Date, nullable=False),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(_EARNING_SOURCE_TYPE_CHECK, name="ck_earnings_source_type"),
    )
    op.create_index("ix_earnings_user_id", "earnings", ["user_id"])
    op.create_index("ix_earnings_transaction_id", "earnings", ["transaction_id"])
    op.create_index("ix_earnings_source_id", "earnings", ["source_id"])
    op.create_index("ix_earnings_date", "earnings", ["date"])

    # ── earnings_outbox ───────────────────────────────────────────────────────
    op.create_table(
        "earnings_outbox",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column("payload", postgresql.JSONB, nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
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
    op.create_index("ix_earnings_outbox_event_type", "earnings_outbox", ["event_type"])
    op.create_index("ix_earnings_outbox_status", "earnings_outbox", ["status"])


def downgrade() -> None:
    op.drop_table("earnings_outbox")
    op.drop_table("earnings")
    op.drop_table("earning_sources")
