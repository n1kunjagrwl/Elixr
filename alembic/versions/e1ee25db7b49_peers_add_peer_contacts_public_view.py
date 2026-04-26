"""peers: add peer_contacts_public view

Revision ID: e1ee25db7b49
Revises: c67a686e7eff
Create Date: 2026-04-25 17:05:26.128349

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'e1ee25db7b49'
down_revision: Union[str, None] = 'c67a686e7eff'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE VIEW peer_contacts_public AS
        SELECT id, user_id, name
        FROM peer_contacts
        """
    )


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS peer_contacts_public")
