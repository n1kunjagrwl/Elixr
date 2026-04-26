from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from elixir.domains.investments.repositories import InvestmentsRepository
from elixir.domains.investments.schemas import (
    FDDetailsCreate,
    FDDetailsResponse,
    HoldingCreate,
    HoldingResponse,
    HoldingUpdate,
    InstrumentCreate,
    InstrumentResponse,
    SIPCreate,
    SIPResponse,
    SIPUpdate,
)
from elixir.shared.exceptions import (
    DuplicateHoldingError,
    FDDetailsAlreadyExistError,
    FDDetailsRequiredError,
    HoldingNotFoundError,
    InstrumentNotFoundError,
    SIPNotFoundError,
)


def compute_maturity_amount(
    principal: Decimal,
    rate_percent: Decimal,
    tenure_days: int,
    compounding: str,
) -> Decimal:
    """
    Compute FD maturity amount using compound (or simple) interest.

    Formulae:
      simple:    P * (1 + r * t)
      otherwise: P * (1 + r/n) ^ (n * t)

    where t = tenure_days / 365 and n is compounding periods per year.
    """
    P = Decimal(str(principal))
    r = Decimal(str(rate_percent)) / 100
    t = Decimal(str(tenure_days)) / 365

    if compounding == "simple":
        return P * (1 + r * t)

    n_map = {"monthly": 12, "quarterly": 4, "annually": 1}
    n = Decimal(str(n_map[compounding]))
    return P * ((1 + r / n) ** (n * t))


class InvestmentsService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._repo = InvestmentsRepository(db)

    # ── Instruments ───────────────────────────────────────────────────────────

    async def search_instruments(
        self, q: str | None = None, type_filter: str | None = None
    ) -> list[InstrumentResponse]:
        instruments = await self._repo.search_instruments(q=q, type_filter=type_filter)
        return [InstrumentResponse.model_validate(i) for i in instruments]

    async def create_instrument(self, data: InstrumentCreate) -> InstrumentResponse:
        inst = await self._repo.create_instrument(
            name=data.name,
            type_=data.type,
            currency=data.currency,
            ticker=data.ticker,
            isin=data.isin,
            exchange=data.exchange,
            data_source=data.data_source,
            govt_rate_percent=data.govt_rate_percent,
        )
        await self._db.commit()
        return InstrumentResponse.model_validate(inst)

    # ── Holdings ──────────────────────────────────────────────────────────────

    async def list_holdings(self, user_id: uuid.UUID) -> list[HoldingResponse]:
        holdings = await self._repo.list_holdings(user_id)
        return [HoldingResponse.model_validate(h) for h in holdings]

    async def add_holding(
        self, user_id: uuid.UUID, data: HoldingCreate
    ) -> HoldingResponse:
        inst = await self._repo.get_instrument(data.instrument_id)
        if inst is None:
            raise InstrumentNotFoundError(f"Instrument {data.instrument_id} not found.")

        existing = await self._repo.get_holding_by_instrument(user_id, data.instrument_id)
        if existing is not None:
            raise DuplicateHoldingError(
                f"Holding for instrument {data.instrument_id} already exists."
            )

        holding = await self._repo.create_holding(
            user_id=user_id,
            instrument_id=data.instrument_id,
            units=data.units,
            avg_cost_per_unit=data.avg_cost_per_unit,
            total_invested=data.total_invested,
            current_value=data.current_value,
            current_price=data.current_price,
        )
        await self._db.commit()
        return HoldingResponse.model_validate(holding)

    async def edit_holding(
        self,
        user_id: uuid.UUID,
        holding_id: uuid.UUID,
        data: HoldingUpdate,
    ) -> HoldingResponse:
        holding = await self._repo.get_holding(user_id, holding_id)
        if holding is None:
            raise HoldingNotFoundError(f"Holding {holding_id} not found.")

        update_fields = data.model_dump(exclude_unset=True, exclude_none=True)
        if update_fields:
            await self._repo.update_holding(holding, **update_fields)
        await self._db.commit()
        return HoldingResponse.model_validate(holding)

    async def remove_holding(self, user_id: uuid.UUID, holding_id: uuid.UUID) -> None:
        holding = await self._repo.get_holding(user_id, holding_id)
        if holding is None:
            raise HoldingNotFoundError(f"Holding {holding_id} not found.")
        await self._repo.delete_holding(holding)
        await self._db.commit()

    # ── FD Details ────────────────────────────────────────────────────────────

    async def add_fd_details(
        self,
        user_id: uuid.UUID,
        holding_id: uuid.UUID,
        data: FDDetailsCreate,
    ) -> FDDetailsResponse:
        holding = await self._repo.get_holding(user_id, holding_id)
        if holding is None:
            raise HoldingNotFoundError(f"Holding {holding_id} not found.")

        inst = await self._repo.get_instrument(holding.instrument_id)
        if inst is None or inst.type != "fd":
            raise FDDetailsRequiredError(
                "FD details can only be added to a holding of type 'fd'."
            )

        existing_fd = await self._repo.get_fd_details(holding_id)
        if existing_fd is not None:
            raise FDDetailsAlreadyExistError(
                f"FD details already exist for holding {holding_id}."
            )

        maturity_amount = compute_maturity_amount(
            principal=data.principal,
            rate_percent=data.rate_percent,
            tenure_days=data.tenure_days,
            compounding=data.compounding,
        )

        fd = await self._repo.create_fd_details(
            holding_id=holding_id,
            principal=data.principal,
            rate_percent=data.rate_percent,
            tenure_days=data.tenure_days,
            start_date=data.start_date,
            maturity_date=data.maturity_date,
            compounding=data.compounding,
            maturity_amount=maturity_amount,
        )
        await self._db.commit()
        return FDDetailsResponse.model_validate(fd)

    # ── Portfolio History ─────────────────────────────────────────────────────

    async def get_portfolio_history(
        self,
        user_id: uuid.UUID,
        from_date: date | None = None,
        to_date: date | None = None,
    ) -> list[dict]:
        return await self._repo.list_portfolio_history(
            user_id=user_id,
            from_date=from_date,
            to_date=to_date,
        )

    # ── SIP Registrations ─────────────────────────────────────────────────────

    async def list_sips(self, user_id: uuid.UUID) -> list[SIPResponse]:
        sips = await self._repo.list_sips(user_id)
        return [SIPResponse.model_validate(s) for s in sips]

    async def register_sip(self, user_id: uuid.UUID, data: SIPCreate) -> SIPResponse:
        inst = await self._repo.get_instrument(data.instrument_id)
        if inst is None:
            raise InstrumentNotFoundError(f"Instrument {data.instrument_id} not found.")

        sip = await self._repo.create_sip(
            user_id=user_id,
            instrument_id=data.instrument_id,
            amount=data.amount,
            frequency=data.frequency,
            debit_day=data.debit_day,
            bank_account_id=data.bank_account_id,
        )
        await self._db.commit()
        return SIPResponse.model_validate(sip)

    async def edit_sip(
        self,
        user_id: uuid.UUID,
        sip_id: uuid.UUID,
        data: SIPUpdate,
    ) -> SIPResponse:
        sip = await self._repo.get_sip(user_id, sip_id)
        if sip is None:
            raise SIPNotFoundError(f"SIP {sip_id} not found.")

        update_fields = data.model_dump(exclude_unset=True, exclude_none=True)
        if update_fields:
            await self._repo.update_sip(sip, **update_fields)
        await self._db.commit()
        return SIPResponse.model_validate(sip)

    async def deactivate_sip(self, user_id: uuid.UUID, sip_id: uuid.UUID) -> None:
        sip = await self._repo.get_sip(user_id, sip_id)
        if sip is None:
            raise SIPNotFoundError(f"SIP {sip_id} not found.")
        await self._repo.deactivate_sip(sip)
        await self._db.commit()

    async def confirm_sip_link(
        self, user_id: uuid.UUID, sip_id: uuid.UUID, transaction_id: uuid.UUID
    ) -> None:
        sip = await self._repo.get_sip(user_id, sip_id)
        if sip is None:
            raise SIPNotFoundError(f"SIP {sip_id} not found.")

        await self._repo.add_outbox_event(
            "investments.SIPLinked",
            {
                "transaction_id": str(transaction_id),
                "sip_registration_id": str(sip_id),
                "user_id": str(user_id),
            },
        )
        await self._db.commit()

    # ── Event handlers ────────────────────────────────────────────────────────

    async def handle_account_removed(self, payload: dict) -> None:
        """
        Subscribed to accounts.AccountRemoved.
        Deactivates all SIPs whose bank_account_id matches the removed account.
        """
        account_id = uuid.UUID(payload["account_id"])
        await self._repo.deactivate_sips_for_account(account_id)

    async def handle_transaction_created(self, payload: dict) -> None:
        """
        Subscribed to transactions.TransactionCreated.
        Checks whether the debit matches any active SIP; if so, writes SIPDetected to outbox.

        Match criteria (all must pass):
          - transaction type is 'debit'
          - amount within ±2% of sip.amount
          - transaction date within ±3 days of sip.debit_day in the same month
          - bank_account_id matches sip.bank_account_id

        Idempotent: skips writing if outbox row already exists for
        (transaction_id, sip_registration_id).
        """
        if payload.get("type") != "debit":
            return

        user_id = uuid.UUID(payload["user_id"])
        transaction_id = payload["transaction_id"]
        txn_amount = Decimal(str(payload["amount"]))
        txn_date = _parse_date(payload["date"])
        bank_account_id = payload.get("bank_account_id")

        active_sips = await self._repo.list_active_sips_for_user(user_id)

        for sip in active_sips:
            # bank account must match
            if bank_account_id is None or str(sip.bank_account_id) != bank_account_id:
                continue

            # amount within ±2%
            sip_amount = Decimal(str(sip.amount))
            if sip_amount == 0:
                continue
            ratio = abs(txn_amount - sip_amount) / sip_amount
            if ratio > Decimal("0.02"):
                continue

            # date within ±3 days of debit_day
            if sip.debit_day is not None:
                day_diff = abs(txn_date.day - sip.debit_day)
                # wrap around month boundary (e.g. day 1 vs day 30 → diff 3)
                days_in_month = _days_in_month(txn_date.year, txn_date.month)
                day_diff = min(day_diff, days_in_month - day_diff)
                if day_diff > 3:
                    continue

            # idempotency check
            already_exists = await self._repo.outbox_event_exists(
                "investments.SIPDetected", transaction_id, str(sip.id)
            )
            if already_exists:
                continue

            await self._repo.add_outbox_event(
                "investments.SIPDetected",
                {
                    "transaction_id": transaction_id,
                    "user_id": str(user_id),
                    "sip_registration_id": str(sip.id),
                    "amount": str(txn_amount),
                    "instrument_name": "",  # enriched by event consumer if needed
                },
            )


def _parse_date(value: str) -> date:
    """Parse an ISO date string (YYYY-MM-DD) to a date object."""
    from datetime import datetime

    return datetime.fromisoformat(value).date()


def _days_in_month(year: int, month: int) -> int:
    import calendar

    return calendar.monthrange(year, month)[1]
