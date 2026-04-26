from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from elixir.domains.investments.models import (
    FDDetails,
    Holding,
    Instrument,
    InvestmentsOutbox,
    SIPRegistration,
    ValuationSnapshot,
)


class InvestmentsRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    # ── Instruments ───────────────────────────────────────────────────────────

    async def search_instruments(
        self, q: str | None = None, type_filter: str | None = None
    ) -> list[Instrument]:
        stmt = select(Instrument)
        if q:
            stmt = stmt.where(Instrument.name.ilike(f"%{q}%"))
        if type_filter:
            stmt = stmt.where(Instrument.type == type_filter)
        stmt = stmt.order_by(Instrument.name)
        result = await self._db.execute(stmt)
        return list(result.scalars().all())

    async def get_instrument(self, instrument_id: uuid.UUID) -> Instrument | None:
        result = await self._db.execute(
            select(Instrument).where(Instrument.id == instrument_id)
        )
        return result.scalar_one_or_none()

    async def create_instrument(
        self,
        name: str,
        type_: str,
        currency: str = "INR",
        ticker: str | None = None,
        isin: str | None = None,
        exchange: str | None = None,
        data_source: str | None = None,
        govt_rate_percent: Decimal | None = None,
    ) -> Instrument:
        inst = Instrument(
            name=name,
            type=type_,
            currency=currency,
            ticker=ticker,
            isin=isin,
            exchange=exchange,
            data_source=data_source,
            govt_rate_percent=govt_rate_percent,
        )
        self._db.add(inst)
        await self._db.flush()
        return inst

    # ── Holdings ──────────────────────────────────────────────────────────────

    async def list_holdings(self, user_id: uuid.UUID) -> list[Holding]:
        result = await self._db.execute(
            select(Holding).where(Holding.user_id == user_id).order_by(Holding.created_at)
        )
        return list(result.scalars().all())

    async def get_holding(self, user_id: uuid.UUID, holding_id: uuid.UUID) -> Holding | None:
        result = await self._db.execute(
            select(Holding).where(
                Holding.id == holding_id,
                Holding.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_holding_by_instrument(
        self, user_id: uuid.UUID, instrument_id: uuid.UUID
    ) -> Holding | None:
        result = await self._db.execute(
            select(Holding).where(
                Holding.user_id == user_id,
                Holding.instrument_id == instrument_id,
            )
        )
        return result.scalar_one_or_none()

    async def create_holding(
        self,
        user_id: uuid.UUID,
        instrument_id: uuid.UUID,
        units: Decimal | None = None,
        avg_cost_per_unit: Decimal | None = None,
        total_invested: Decimal | None = None,
        current_value: Decimal | None = None,
        current_price: Decimal | None = None,
    ) -> Holding:
        holding = Holding(
            user_id=user_id,
            instrument_id=instrument_id,
            units=units,
            avg_cost_per_unit=avg_cost_per_unit,
            total_invested=total_invested,
            current_value=current_value,
            current_price=current_price,
        )
        self._db.add(holding)
        await self._db.flush()
        return holding

    async def update_holding(self, holding: Holding, **fields: Any) -> None:
        for key, value in fields.items():
            if value is not None:
                setattr(holding, key, value)
        holding.updated_at = datetime.now(timezone.utc)

    async def delete_holding(self, holding: Holding) -> None:
        await self._db.delete(holding)

    # ── FD Details ────────────────────────────────────────────────────────────

    async def get_fd_details(self, holding_id: uuid.UUID) -> FDDetails | None:
        result = await self._db.execute(
            select(FDDetails).where(FDDetails.holding_id == holding_id)
        )
        return result.scalar_one_or_none()

    async def create_fd_details(
        self,
        holding_id: uuid.UUID,
        principal: Decimal,
        rate_percent: Decimal,
        tenure_days: int,
        start_date: date,
        maturity_date: date,
        compounding: str,
        maturity_amount: Decimal | None = None,
    ) -> FDDetails:
        fd = FDDetails(
            holding_id=holding_id,
            principal=principal,
            rate_percent=rate_percent,
            tenure_days=tenure_days,
            start_date=start_date,
            maturity_date=maturity_date,
            compounding=compounding,
            maturity_amount=maturity_amount,
        )
        self._db.add(fd)
        await self._db.flush()
        return fd

    # ── Valuation Snapshots ───────────────────────────────────────────────────

    async def upsert_valuation_snapshot(
        self,
        holding_id: uuid.UUID,
        price: Decimal,
        value: Decimal,
        snapshot_date: date,
    ) -> None:
        """
        INSERT ... ON CONFLICT (holding_id, snapshot_date) DO UPDATE
        so daily runs are idempotent.
        """
        stmt = (
            pg_insert(ValuationSnapshot)
            .values(
                holding_id=holding_id,
                price=price,
                value=value,
                snapshot_date=snapshot_date,
            )
            .on_conflict_do_update(
                constraint="uq_valuation_snapshots_holding_date",
                set_={"price": price, "value": value},
            )
        )
        await self._db.execute(stmt)

    async def list_portfolio_history(
        self,
        user_id: uuid.UUID,
        from_date: date | None = None,
        to_date: date | None = None,
    ) -> list[dict[str, Any]]:
        """
        Returns daily portfolio totals by summing valuation snapshots
        for all holdings belonging to user_id, filtered by date range.
        """
        from sqlalchemy import func

        stmt = (
            select(
                ValuationSnapshot.snapshot_date,
                func.sum(ValuationSnapshot.value).label("total_value"),
            )
            .join(Holding, ValuationSnapshot.holding_id == Holding.id)
            .where(Holding.user_id == user_id)
        )
        if from_date:
            stmt = stmt.where(ValuationSnapshot.snapshot_date >= from_date)
        if to_date:
            stmt = stmt.where(ValuationSnapshot.snapshot_date <= to_date)
        stmt = stmt.group_by(ValuationSnapshot.snapshot_date).order_by(
            ValuationSnapshot.snapshot_date
        )
        result = await self._db.execute(stmt)
        rows = result.mappings().all()
        return [
            {
                "snapshot_date": row["snapshot_date"].isoformat()
                if hasattr(row["snapshot_date"], "isoformat")
                else str(row["snapshot_date"]),
                "total_value": str(row["total_value"]),
            }
            for row in rows
        ]

    # ── SIP Registrations ─────────────────────────────────────────────────────

    async def list_sips(self, user_id: uuid.UUID) -> list[SIPRegistration]:
        result = await self._db.execute(
            select(SIPRegistration).where(SIPRegistration.user_id == user_id)
        )
        return list(result.scalars().all())

    async def get_sip(self, user_id: uuid.UUID, sip_id: uuid.UUID) -> SIPRegistration | None:
        result = await self._db.execute(
            select(SIPRegistration).where(
                SIPRegistration.id == sip_id,
                SIPRegistration.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    async def create_sip(
        self,
        user_id: uuid.UUID,
        instrument_id: uuid.UUID,
        amount: Decimal,
        frequency: str,
        debit_day: int | None = None,
        bank_account_id: uuid.UUID | None = None,
    ) -> SIPRegistration:
        sip = SIPRegistration(
            user_id=user_id,
            instrument_id=instrument_id,
            amount=amount,
            frequency=frequency,
            debit_day=debit_day,
            bank_account_id=bank_account_id,
        )
        self._db.add(sip)
        await self._db.flush()
        return sip

    async def update_sip(self, sip: SIPRegistration, **fields: Any) -> None:
        for key, value in fields.items():
            if value is not None:
                setattr(sip, key, value)
        sip.updated_at = datetime.now(timezone.utc)

    async def deactivate_sip(self, sip: SIPRegistration) -> None:
        sip.is_active = False
        sip.updated_at = datetime.now(timezone.utc)

    async def deactivate_sips_for_account(self, bank_account_id: uuid.UUID) -> None:
        """Batch-deactivate all SIPs linked to the given bank account."""
        await self._db.execute(
            update(SIPRegistration)
            .where(
                SIPRegistration.bank_account_id == bank_account_id,
                SIPRegistration.is_active.is_(True),
            )
            .values(is_active=False, updated_at=datetime.now(timezone.utc))
        )

    async def list_active_sips_for_user(self, user_id: uuid.UUID) -> list[SIPRegistration]:
        result = await self._db.execute(
            select(SIPRegistration).where(
                SIPRegistration.user_id == user_id,
                SIPRegistration.is_active.is_(True),
            )
        )
        return list(result.scalars().all())

    # ── Outbox ────────────────────────────────────────────────────────────────

    async def add_outbox_event(
        self, event_type: str, payload: dict[str, Any]
    ) -> None:
        row = InvestmentsOutbox(event_type=event_type, payload=payload)
        self._db.add(row)

    async def outbox_event_exists(
        self, event_type: str, transaction_id: str, sip_id: str
    ) -> bool:
        """
        Check if a SIPDetected outbox row already exists for this
        (transaction_id, sip_registration_id) pair — idempotency guard.
        """
        from sqlalchemy import and_

        result = await self._db.execute(
            select(InvestmentsOutbox.id).where(
                and_(
                    InvestmentsOutbox.event_type == event_type,
                    InvestmentsOutbox.payload["transaction_id"].astext == transaction_id,
                    InvestmentsOutbox.payload["sip_registration_id"].astext == sip_id,
                )
            )
        )
        return result.scalar_one_or_none() is not None
