"""categorization: add categories rules outbox seed defaults

Revision ID: 3d053ced9c56
Revises: 2eed9bab9c27
Create Date: 2026-04-25 16:43:03.314888

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = '3d053ced9c56'
down_revision: Union[str, None] = '2eed9bab9c27'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── categories ─────────────────────────────────────────────────────────────
    op.create_table(
        'categories',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('slug', sa.String(255), nullable=False),
        sa.Column('kind', sa.String(20), nullable=False),
        sa.Column('parent_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('icon', sa.String(50), nullable=True),
        sa.Column('is_default', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("kind IN ('expense','income','transfer')", name='ck_categories_kind'),
        sa.ForeignKeyConstraint(['parent_id'], ['categories.id'], ondelete='SET NULL'),
    )
    op.create_index('ix_categories_user_id', 'categories', ['user_id'])

    # ── categorization_rules ───────────────────────────────────────────────────
    op.create_table(
        'categorization_rules',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('pattern', sa.String(500), nullable=False),
        sa.Column('match_type', sa.String(20), nullable=False),
        sa.Column('category_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('priority', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "match_type IN ('contains','starts_with','exact','regex')",
            name='ck_categorization_rules_match_type',
        ),
        sa.ForeignKeyConstraint(['category_id'], ['categories.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_categorization_rules_user_id', 'categorization_rules', ['user_id'])

    # ── categorization_outbox ──────────────────────────────────────────────────
    op.create_table(
        'categorization_outbox',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('event_type', sa.String(100), nullable=False),
        sa.Column('payload', postgresql.JSONB(), nullable=False),
        sa.Column('status', sa.String(20), nullable=False, server_default='pending'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('processed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('attempt_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('last_error', sa.String(1000), nullable=True),
    )
    op.create_index('ix_categorization_outbox_event_type', 'categorization_outbox', ['event_type'])
    op.create_index('ix_categorization_outbox_status', 'categorization_outbox', ['status'])

    # ── Seed default categories ────────────────────────────────────────────────
    op.execute("""
        INSERT INTO categories (id, user_id, name, slug, kind, is_default, is_active)
        VALUES
            -- Expense categories (15)
            (gen_random_uuid(), NULL, 'Food & Dining',    'food-dining',    'expense', true, true),
            (gen_random_uuid(), NULL, 'Groceries',        'groceries',      'expense', true, true),
            (gen_random_uuid(), NULL, 'Transport',        'transport',      'expense', true, true),
            (gen_random_uuid(), NULL, 'Utilities',        'utilities',      'expense', true, true),
            (gen_random_uuid(), NULL, 'Shopping',         'shopping',       'expense', true, true),
            (gen_random_uuid(), NULL, 'Health & Medical', 'health-medical', 'expense', true, true),
            (gen_random_uuid(), NULL, 'Entertainment',    'entertainment',  'expense', true, true),
            (gen_random_uuid(), NULL, 'Travel',           'travel',         'expense', true, true),
            (gen_random_uuid(), NULL, 'Education',        'education',      'expense', true, true),
            (gen_random_uuid(), NULL, 'Personal Care',    'personal-care',  'expense', true, true),
            (gen_random_uuid(), NULL, 'Subscriptions',    'subscriptions',  'expense', true, true),
            (gen_random_uuid(), NULL, 'EMI & Loans',      'emi-loans',      'expense', true, true),
            (gen_random_uuid(), NULL, 'Rent',             'rent',           'expense', true, true),
            (gen_random_uuid(), NULL, 'Investments',      'investments',    'expense', true, true),
            (gen_random_uuid(), NULL, 'Others',           'others',         'expense', true, true),
            -- Income categories (6)
            (gen_random_uuid(), NULL, 'Salary',           'salary',         'income',  true, true),
            (gen_random_uuid(), NULL, 'Freelance',        'freelance',      'income',  true, true),
            (gen_random_uuid(), NULL, 'Rental Income',    'rental-income',  'income',  true, true),
            (gen_random_uuid(), NULL, 'Dividends',        'dividends',      'income',  true, true),
            (gen_random_uuid(), NULL, 'Interest',         'interest',       'income',  true, true),
            (gen_random_uuid(), NULL, 'Business Income',  'business-income','income',  true, true),
            -- Transfer categories (1)
            (gen_random_uuid(), NULL, 'Self Transfer',    'self-transfer',  'transfer',true, true)
        ON CONFLICT DO NOTHING;
    """)


def downgrade() -> None:
    op.drop_table('categorization_outbox')
    op.drop_table('categorization_rules')
    op.drop_table('categories')
