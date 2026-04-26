from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import ClassVar

from sqlalchemy.ext.asyncio import AsyncSession


@dataclass
class EarningRecorded:
    event_type: ClassVar[str] = "earnings.EarningRecorded"

    earning_id: uuid.UUID
    user_id: uuid.UUID
    source_type: str
    amount: Decimal
    currency: str
    date: date

    def to_payload(self) -> dict:
        return {
            "earning_id": str(self.earning_id),
            "user_id": str(self.user_id),
            "source_type": self.source_type,
            "amount": str(self.amount),
            "currency": self.currency,
            "date": self.date.isoformat(),
        }


@dataclass
class EarningClassificationNeeded:
    event_type: ClassVar[str] = "earnings.EarningClassificationNeeded"

    transaction_id: uuid.UUID
    user_id: uuid.UUID
    amount: Decimal
    currency: str
    description: str

    def to_payload(self) -> dict:
        return {
            "transaction_id": str(self.transaction_id),
            "user_id": str(self.user_id),
            "amount": str(self.amount),
            "currency": self.currency,
            "description": self.description,
        }


async def handle_transaction_created(payload: dict, session: AsyncSession) -> None:
    from elixir.domains.earnings.services import EarningsService

    service = EarningsService(db=session)
    await service.handle_transaction_created(payload)
