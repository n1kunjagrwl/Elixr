"""accounts: add bank_accounts credit_cards accounts_outbox

Revision ID: 01bffb70d97e
Revises: 001_identity
Create Date: 2026-04-25 16:26:01.360174

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "01bffb70d97e"
down_revision: Union[str, None] = "001_identity"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "bank_accounts",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("nickname", sa.String(255), nullable=False),
        sa.Column("bank_name", sa.String(255), nullable=False),
        sa.Column("account_type", sa.String(20), nullable=False),
        sa.Column("last4", sa.String(4), nullable=True),
        sa.Column("currency", sa.String(3), nullable=False, server_default="INR"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "account_type IN ('savings','current','salary','nre','nro')",
            name="ck_bank_accounts_account_type",
        ),
    )
    op.create_index("ix_bank_accounts_user_id", "bank_accounts", ["user_id"])

    op.create_table(
        "credit_cards",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("nickname", sa.String(255), nullable=False),
        sa.Column("bank_name", sa.String(255), nullable=False),
        sa.Column("card_network", sa.String(20), nullable=True),
        sa.Column("last4", sa.String(4), nullable=True),
        sa.Column("credit_limit", sa.Numeric(15, 2), nullable=True),
        sa.Column("billing_cycle_day", sa.Integer(), nullable=True),
        sa.Column("currency", sa.String(3), nullable=False, server_default="INR"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "card_network IS NULL OR card_network IN ('visa','mastercard','amex','rupay')",
            name="ck_credit_cards_card_network",
        ),
    )
    op.create_index("ix_credit_cards_user_id", "credit_cards", ["user_id"])

    op.create_table(
        "accounts_outbox",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error", sa.String(1000), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_accounts_outbox_status", "accounts_outbox", ["status"])
    op.create_index("ix_accounts_outbox_event_type", "accounts_outbox", ["event_type"])


def downgrade() -> None:
    op.drop_index("ix_accounts_outbox_event_type", "accounts_outbox")
    op.drop_index("ix_accounts_outbox_status", "accounts_outbox")
    op.drop_table("accounts_outbox")
    op.drop_index("ix_credit_cards_user_id", "credit_cards")
    op.drop_table("credit_cards")
    op.drop_index("ix_bank_accounts_user_id", "bank_accounts")
    op.drop_table("bank_accounts")
