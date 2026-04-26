"""transactions: add transactions_with_categories view

Revision ID: 7c1e29c7372f
Revises: 0a8339950b5f
Create Date: 2026-04-26 00:51:05.486242

"""
from typing import Sequence, Union

from alembic import op

revision: str = '7c1e29c7372f'
down_revision: Union[str, None] = '0a8339950b5f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE VIEW transactions_with_categories AS
        SELECT
            t.id,
            t.user_id,
            t.account_id,
            t.account_kind,
            t.amount,
            t.currency,
            t.date,
            t.type,
            t.source,
            t.raw_description,
            t.notes,
            ti.id        AS item_id,
            ti.category_id,
            ti.amount    AS item_amount,
            ti.currency  AS item_currency,
            ti.label,
            ti.is_primary
        FROM transactions t
        JOIN transaction_items ti ON ti.transaction_id = t.id
        """
    )


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS transactions_with_categories")
