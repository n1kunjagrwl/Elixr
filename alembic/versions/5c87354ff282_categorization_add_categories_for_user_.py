"""categorization: add categories_for_user view

Revision ID: 5c87354ff282
Revises: 3d053ced9c56
Create Date: 2026-04-25 16:44:56.539673

"""
from typing import Sequence, Union

from alembic import op

revision: str = '5c87354ff282'
down_revision: Union[str, None] = '3d053ced9c56'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE VIEW categories_for_user AS
        SELECT id, name, slug, kind, icon, is_default, parent_id,
               NULL::uuid AS user_id, is_active, created_at, updated_at
        FROM categories
        WHERE user_id IS NULL
          AND is_active = true
        UNION ALL
        SELECT id, name, slug, kind, icon, is_default, parent_id,
               user_id, is_active, created_at, updated_at
        FROM categories
        WHERE user_id IS NOT NULL
          AND is_active = true;
    """)


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS categories_for_user;")
