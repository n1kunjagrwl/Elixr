"""transactions: add transactions transaction_items transactions_outbox

Revision ID: 0a8339950b5f
Revises: 69d337c9fb49
Create Date: 2026-04-26 00:49:53.189933

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = '0a8339950b5f'
down_revision: Union[str, None] = '69d337c9fb49'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── transactions ──────────────────────────────────────────────────────────
    op.create_table(
        'transactions',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('account_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('account_kind', sa.String(20), nullable=False),
        sa.Column('amount', sa.Numeric(15, 2), nullable=False),
        sa.Column('currency', sa.String(3), nullable=False, server_default='INR'),
        sa.Column('date', sa.Date, nullable=False),
        sa.Column('type', sa.String(20), nullable=False),
        sa.Column('source', sa.String(30), nullable=False),
        sa.Column('raw_description', sa.Text, nullable=True),
        sa.Column('notes', sa.Text, nullable=True),
        sa.Column('fingerprint', sa.Text, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "account_kind IN ('bank','credit_card')",
            name='ck_transactions_account_kind',
        ),
        sa.CheckConstraint(
            "type IN ('debit','credit','transfer')",
            name='ck_transactions_type',
        ),
        sa.CheckConstraint(
            "source IN ('manual','statement_import','recurring_detected','bulk_import')",
            name='ck_transactions_source',
        ),
    )
    op.create_index('ix_transactions_user_id', 'transactions', ['user_id'])
    op.create_index('ix_transactions_account_id', 'transactions', ['account_id'])
    op.create_index('ix_transactions_date', 'transactions', ['date'])

    # Partial unique index: enforce fingerprint uniqueness only when fingerprint IS NOT NULL
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_transactions_user_fingerprint "
        "ON transactions (user_id, fingerprint) WHERE fingerprint IS NOT NULL"
    )

    # ── transaction_items ────────────────────────────────────────────────────
    op.create_table(
        'transaction_items',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            'transaction_id',
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey('transactions.id', ondelete='CASCADE'),
            nullable=False,
        ),
        sa.Column('category_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('amount', sa.Numeric(15, 2), nullable=False),
        sa.Column('currency', sa.String(3), nullable=False, server_default='INR'),
        sa.Column('label', sa.Text, nullable=True),
        sa.Column('is_primary', sa.Boolean, nullable=False, server_default='false'),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index('ix_transaction_items_transaction_id', 'transaction_items', ['transaction_id'])
    op.create_index('ix_transaction_items_category_id', 'transaction_items', ['category_id'])

    # ── transactions_outbox ──────────────────────────────────────────────────
    op.create_table(
        'transactions_outbox',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('event_type', sa.String(100), nullable=False),
        sa.Column('payload', postgresql.JSONB, nullable=False),
        sa.Column('status', sa.String(20), nullable=False, server_default='pending'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('processed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('attempt_count', sa.Integer, nullable=False, server_default='0'),
        sa.Column('last_error', sa.String(1000), nullable=True),
    )
    op.create_index('ix_transactions_outbox_event_type', 'transactions_outbox', ['event_type'])
    op.create_index('ix_transactions_outbox_status', 'transactions_outbox', ['status'])


def downgrade() -> None:
    op.drop_table('transactions_outbox')
    op.drop_table('transaction_items')
    op.drop_index('uq_transactions_user_fingerprint', table_name='transactions')
    op.drop_index('ix_transactions_date', table_name='transactions')
    op.drop_index('ix_transactions_account_id', table_name='transactions')
    op.drop_index('ix_transactions_user_id', table_name='transactions')
    op.drop_table('transactions')
