"""budgets: add budget_goals budget_progress budget_alerts budgets_outbox

Revision ID: 0b449bfcc88f
Revises: 3d17d3b12aac
Create Date: 2026-04-26 01:39:45.857298

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = '0b449bfcc88f'
down_revision: Union[str, None] = '3d17d3b12aac'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── budget_goals ──────────────────────────────────────────────────────────
    op.create_table(
        "budget_goals",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("category_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("limit_amount", sa.Numeric(15, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="INR"),
        sa.Column("period_type", sa.String(20), nullable=False),
        sa.Column("period_anchor_day", sa.Integer, nullable=True),
        sa.Column("custom_start", sa.Date, nullable=True),
        sa.Column("custom_end", sa.Date, nullable=True),
        sa.Column("rollover", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "period_type IN ('monthly','weekly','custom')",
            name="ck_budget_goals_period_type",
        ),
        sa.CheckConstraint(
            "period_anchor_day IS NULL OR (period_anchor_day >= 1 AND period_anchor_day <= 28)",
            name="ck_budget_goals_anchor_day",
        ),
    )
    op.create_index("ix_budget_goals_user_id", "budget_goals", ["user_id"])
    op.create_index("ix_budget_goals_category_id", "budget_goals", ["category_id"])

    # ── budget_progress ───────────────────────────────────────────────────────
    op.create_table(
        "budget_progress",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "goal_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("budget_goals.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("period_start", sa.Date, nullable=False),
        sa.Column("period_end", sa.Date, nullable=False),
        sa.Column("current_spend", sa.Numeric(15, 2), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("goal_id", "period_start", name="uq_budget_progress_goal_period"),
    )
    op.create_index("ix_budget_progress_goal_id", "budget_progress", ["goal_id"])
    op.create_index("ix_budget_progress_user_id", "budget_progress", ["user_id"])

    # ── budget_alerts ─────────────────────────────────────────────────────────
    op.create_table(
        "budget_alerts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "goal_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("budget_goals.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("triggered_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("threshold_percent", sa.Integer, nullable=False),
        sa.Column("current_spend", sa.Numeric(15, 2), nullable=False),
        sa.Column("period_start", sa.Date, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "goal_id", "period_start", "threshold_percent",
            name="uq_budget_alerts_goal_period_threshold",
        ),
        sa.CheckConstraint(
            "threshold_percent IN (80, 100)",
            name="ck_budget_alerts_threshold_percent",
        ),
    )
    op.create_index("ix_budget_alerts_goal_id", "budget_alerts", ["goal_id"])

    # ── budgets_outbox ────────────────────────────────────────────────────────
    op.create_table(
        "budgets_outbox",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column("payload", postgresql.JSONB, nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attempt_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("last_error", sa.String(1000), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_budgets_outbox_event_type", "budgets_outbox", ["event_type"])
    op.create_index("ix_budgets_outbox_status", "budgets_outbox", ["status"])


def downgrade() -> None:
    op.drop_table("budgets_outbox")
    op.drop_table("budget_alerts")
    op.drop_table("budget_progress")
    op.drop_table("budget_goals")
