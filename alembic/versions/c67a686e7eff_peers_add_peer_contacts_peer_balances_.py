"""peers: add peer_contacts peer_balances peer_settlements

Revision ID: c67a686e7eff
Revises: 56fc6b939d79
Create Date: 2026-04-25 17:04:42.990474

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 'c67a686e7eff'
down_revision: Union[str, None] = '56fc6b939d79'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── peer_contacts ─────────────────────────────────────────────────────────
    op.create_table(
        "peer_contacts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("phone", sa.String(20), nullable=True),
        sa.Column("notes", sa.String(1000), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_peer_contacts_user_id", "peer_contacts", ["user_id"])

    # ── peer_balances ─────────────────────────────────────────────────────────
    op.create_table(
        "peer_balances",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "peer_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("peer_contacts.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("description", sa.String(500), nullable=False),
        sa.Column("original_amount", sa.Numeric(15, 2), nullable=False),
        sa.Column(
            "settled_amount",
            sa.Numeric(15, 2),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "remaining_amount",
            sa.Numeric(15, 2),
            sa.Computed("original_amount - settled_amount", persisted=True),
            nullable=False,
        ),
        sa.Column("currency", sa.String(3), nullable=False, server_default="INR"),
        sa.Column("direction", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="open"),
        sa.Column("linked_transaction_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("notes", sa.String(1000), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "direction IN ('owed_to_me','i_owe')",
            name="ck_peer_balances_direction",
        ),
        sa.CheckConstraint(
            "status IN ('open','partial','settled')",
            name="ck_peer_balances_status",
        ),
    )
    op.create_index("ix_peer_balances_user_id", "peer_balances", ["user_id"])
    op.create_index("ix_peer_balances_peer_id", "peer_balances", ["peer_id"])

    # ── peer_settlements ──────────────────────────────────────────────────────
    op.create_table(
        "peer_settlements",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "balance_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("peer_balances.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("amount", sa.Numeric(15, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="INR"),
        sa.Column("settled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("method", sa.String(20), nullable=True),
        sa.Column("linked_transaction_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("notes", sa.String(1000), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "method IS NULL OR method IN ('cash','upi','bank_transfer','other')",
            name="ck_peer_settlements_method",
        ),
    )
    op.create_index("ix_peer_settlements_balance_id", "peer_settlements", ["balance_id"])


def downgrade() -> None:
    op.drop_table("peer_settlements")
    op.drop_table("peer_balances")
    op.drop_table("peer_contacts")
