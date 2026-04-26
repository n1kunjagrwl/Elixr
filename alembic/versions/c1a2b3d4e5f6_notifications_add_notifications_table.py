"""notifications: add notifications table

Revision ID: c1a2b3d4e5f6
Revises: 0b449bfcc88f
Create Date: 2026-04-26 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 'c1a2b3d4e5f6'
down_revision: Union[str, None] = '0b449bfcc88f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── notifications ─────────────────────────────────────────────────────────
    op.create_table(
        "notifications",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("type", sa.String(100), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("body", sa.String(1000), nullable=False),
        sa.Column("route", sa.String(255), nullable=False),
        sa.Column("primary_entity_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("secondary_entity_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("period_start", sa.Date, nullable=True),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "idx_notifications_user_id_read_at",
        "notifications",
        ["user_id", "read_at"],
    )
    op.create_index(
        "idx_notifications_user_id_created_at",
        "notifications",
        ["user_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("idx_notifications_user_id_created_at", table_name="notifications")
    op.drop_index("idx_notifications_user_id_read_at", table_name="notifications")
    op.drop_table("notifications")
