"""accounts: add user_accounts_summary view

Revision ID: 2eed9bab9c27
Revises: 01bffb70d97e
Create Date: 2026-04-25 16:26:34.281595

"""
from typing import Sequence, Union

from alembic import op

revision: str = "2eed9bab9c27"
down_revision: Union[str, None] = "01bffb70d97e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_CREATE_VIEW = """
CREATE VIEW user_accounts_summary AS
SELECT
    id,
    user_id,
    nickname,
    bank_name,
    'bank'::text AS account_kind,
    account_type AS subtype,
    last4,
    currency,
    is_active
FROM bank_accounts
UNION ALL
SELECT
    id,
    user_id,
    nickname,
    bank_name,
    'credit_card'::text AS account_kind,
    card_network AS subtype,
    last4,
    currency,
    is_active
FROM credit_cards;
"""

_DROP_VIEW = "DROP VIEW IF EXISTS user_accounts_summary;"


def upgrade() -> None:
    op.execute(_CREATE_VIEW)


def downgrade() -> None:
    op.execute(_DROP_VIEW)
