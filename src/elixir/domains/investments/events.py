from __future__ import annotations

import uuid
from dataclasses import dataclass
from decimal import Decimal
from typing import ClassVar

from sqlalchemy.ext.asyncio import AsyncSession


# ── Event dataclasses ─────────────────────────────────────────────────────────

@dataclass
class SIPDetected:
    event_type: ClassVar[str] = "investments.SIPDetected"

    transaction_id: str
    user_id: uuid.UUID
    sip_registration_id: uuid.UUID
    amount: Decimal
    instrument_name: str

    def to_payload(self) -> dict:
        return {
            "transaction_id": self.transaction_id,
            "user_id": str(self.user_id),
            "sip_registration_id": str(self.sip_registration_id),
            "amount": str(self.amount),
            "instrument_name": self.instrument_name,
        }


@dataclass
class SIPLinked:
    event_type: ClassVar[str] = "investments.SIPLinked"

    transaction_id: str
    sip_registration_id: uuid.UUID
    user_id: uuid.UUID

    def to_payload(self) -> dict:
        return {
            "transaction_id": self.transaction_id,
            "sip_registration_id": str(self.sip_registration_id),
            "user_id": str(self.user_id),
        }


@dataclass
class ValuationUpdated:
    event_type: ClassVar[str] = "investments.ValuationUpdated"

    user_id: uuid.UUID
    updated_holding_ids: list[uuid.UUID]
    total_portfolio_value: Decimal

    def to_payload(self) -> dict:
        return {
            "user_id": str(self.user_id),
            "updated_holding_ids": [str(hid) for hid in self.updated_holding_ids],
            "total_portfolio_value": str(self.total_portfolio_value),
        }


# ── Event handlers (subscribed via bootstrap) ─────────────────────────────────

async def handle_account_removed(payload: dict, session: AsyncSession) -> None:
    """
    Subscribed to accounts.AccountRemoved.
    Deactivates all SIPs whose bank_account_id matches the removed account.
    """
    from elixir.domains.investments.services import InvestmentsService

    service = InvestmentsService(db=session)
    await service.handle_account_removed(payload)


async def handle_transaction_created(payload: dict, session: AsyncSession) -> None:
    """
    Subscribed to transactions.TransactionCreated.
    Detects SIP matches and writes SIPDetected events to the outbox.
    """
    from elixir.domains.investments.services import InvestmentsService

    service = InvestmentsService(db=session)
    await service.handle_transaction_created(payload)
