"""investments: add instruments holdings sip_registrations valuation_snapshots fd_details investments_outbox

Revision ID: 3d17d3b12aac
Revises: a707f5ee953b
Create Date: 2026-04-26 01:23:42.305180

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = '3d17d3b12aac'
down_revision: Union[str, None] = 'a707f5ee953b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── instruments (shared master registry — no user_id) ──────────────────────
    op.create_table(
        "instruments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("ticker", sa.String(20), nullable=True),
        sa.Column("isin", sa.String(12), nullable=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("type", sa.String(20), nullable=False),
        sa.Column("exchange", sa.String(10), nullable=True),
        sa.Column("currency", sa.String(3), nullable=False, server_default="INR"),
        sa.Column("data_source", sa.String(20), nullable=True),
        sa.Column(
            "govt_rate_percent", sa.Numeric(6, 3), nullable=True
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "type IN ('stock','mf','etf','fd','ppf','bond','nps','sgb','crypto','gold',"
            "'us_stock','rd','other')",
            name="ck_instruments_type",
        ),
        sa.CheckConstraint(
            "exchange IS NULL OR exchange IN ('NSE','BSE','NYSE','NASDAQ','MCX')",
            name="ck_instruments_exchange",
        ),
        sa.CheckConstraint(
            "data_source IS NULL OR data_source IN "
            "('amfi','eodhd','coingecko','twelve_data','metals_api','calculated')",
            name="ck_instruments_data_source",
        ),
    )

    # ── holdings (per-user) ────────────────────────────────────────────────────
    op.create_table(
        "holdings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column(
            "instrument_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("instruments.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("units", sa.Numeric(20, 6), nullable=True),
        sa.Column("avg_cost_per_unit", sa.Numeric(15, 4), nullable=True),
        sa.Column("total_invested", sa.Numeric(15, 2), nullable=True),
        sa.Column("current_value", sa.Numeric(15, 2), nullable=True),
        sa.Column("current_price", sa.Numeric(15, 4), nullable=True),
        sa.Column("last_valued_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("user_id", "instrument_id", name="uq_holdings_user_instrument"),
    )

    # ── sip_registrations ──────────────────────────────────────────────────────
    op.create_table(
        "sip_registrations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column(
            "instrument_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("instruments.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("amount", sa.Numeric(15, 2), nullable=False),
        sa.Column("frequency", sa.String(20), nullable=False),
        sa.Column("debit_day", sa.Integer, nullable=True),
        sa.Column("bank_account_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "frequency IN ('monthly','weekly','quarterly')",
            name="ck_sip_registrations_frequency",
        ),
    )

    # ── valuation_snapshots (immutable daily log) ──────────────────────────────
    op.create_table(
        "valuation_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "holding_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("holdings.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("price", sa.Numeric(15, 4), nullable=False),
        sa.Column("value", sa.Numeric(15, 2), nullable=False),
        sa.Column("snapshot_date", sa.Date, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "holding_id", "snapshot_date", name="uq_valuation_snapshots_holding_date"
        ),
    )

    # ── fd_details (immutable — no updated_at) ─────────────────────────────────
    op.create_table(
        "fd_details",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "holding_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("holdings.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("principal", sa.Numeric(15, 2), nullable=False),
        sa.Column("rate_percent", sa.Numeric(6, 3), nullable=False),
        sa.Column("tenure_days", sa.Integer, nullable=False),
        sa.Column("start_date", sa.Date, nullable=False),
        sa.Column("maturity_date", sa.Date, nullable=False),
        sa.Column("compounding", sa.String(20), nullable=False),
        sa.Column("maturity_amount", sa.Numeric(15, 2), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "compounding IN ('monthly','quarterly','annually','simple')",
            name="ck_fd_details_compounding",
        ),
        sa.UniqueConstraint("holding_id", name="uq_fd_details_holding"),
    )

    # ── investments_outbox ─────────────────────────────────────────────────────
    op.create_table(
        "investments_outbox",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("event_type", sa.String(100), nullable=False, index=True),
        sa.Column("payload", postgresql.JSONB, nullable=False),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="pending",
            index=True,
        ),
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


def downgrade() -> None:
    op.drop_table("investments_outbox")
    op.drop_table("fd_details")
    op.drop_table("valuation_snapshots")
    op.drop_table("sip_registrations")
    op.drop_table("holdings")
    op.drop_table("instruments")
