"""identity: make otp_requests.code_hash nullable (Twilio Verify manages codes)

Revision ID: d1e2f3a4b5c6
Revises: c1a2b3d4e5f6
Create Date: 2026-04-26 14:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'd1e2f3a4b5c6'
down_revision: Union[str, None] = 'c1a2b3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column('otp_requests', 'code_hash', nullable=True)


def downgrade() -> None:
    op.execute("UPDATE otp_requests SET code_hash = '' WHERE code_hash IS NULL")
    op.alter_column('otp_requests', 'code_hash', nullable=False)
