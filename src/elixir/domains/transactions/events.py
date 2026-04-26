from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import ClassVar

from sqlalchemy.ext.asyncio import AsyncSession


@dataclass
class TransactionCreated:
    event_type: ClassVar[str] = "transactions.TransactionCreated"

    transaction_id: uuid.UUID
    user_id: uuid.UUID
    account_id: uuid.UUID
    amount: Decimal
    currency: str
    date: date
    type: str
    source: str
    raw_description: str | None = None

    def to_payload(self) -> dict:
        return {
            "transaction_id": str(self.transaction_id),
            "user_id": str(self.user_id),
            "account_id": str(self.account_id),
            "amount": str(self.amount),
            "currency": self.currency,
            "date": self.date.isoformat(),
            "type": self.type,
            "source": self.source,
            "raw_description": self.raw_description,
        }


@dataclass
class TransactionCategorized:
    event_type: ClassVar[str] = "transactions.TransactionCategorized"

    transaction_id: uuid.UUID
    user_id: uuid.UUID
    items: list[dict]

    def to_payload(self) -> dict:
        return {
            "transaction_id": str(self.transaction_id),
            "user_id": str(self.user_id),
            "items": self.items,
        }


@dataclass
class TransactionUpdated:
    event_type: ClassVar[str] = "transactions.TransactionUpdated"

    transaction_id: uuid.UUID
    user_id: uuid.UUID
    date: date
    changed_fields: list[str]
    old_items: list[dict] | None
    new_items: list[dict] | None

    def to_payload(self) -> dict:
        return {
            "transaction_id": str(self.transaction_id),
            "user_id": str(self.user_id),
            "date": self.date.isoformat(),
            "changed_fields": self.changed_fields,
            "old_items": self.old_items,
            "new_items": self.new_items,
        }


async def handle_extraction_completed(payload: dict, session: AsyncSession) -> None:
    from elixir.domains.transactions.services import TransactionsService

    service = TransactionsService(db=session)
    await service.create_transactions_from_classified_rows(
        user_id=uuid.UUID(str(payload["user_id"])),
        account_id=uuid.UUID(str(payload["account_id"])),
        account_kind=payload["account_kind"],
        rows=payload.get("classified_rows", []),
        source="statement_import",
    )


async def handle_extraction_partially_completed(
    payload: dict, session: AsyncSession
) -> None:
    from elixir.domains.transactions.services import TransactionsService

    service = TransactionsService(db=session)
    await service.create_transactions_from_classified_rows(
        user_id=uuid.UUID(str(payload["user_id"])),
        account_id=uuid.UUID(str(payload["account_id"])),
        account_kind=payload["account_kind"],
        rows=payload.get("classified_rows", []),
        source="statement_import",
    )


async def handle_import_batch_ready(payload: dict, session: AsyncSession) -> None:
    from elixir.domains.transactions.services import TransactionsService

    service = TransactionsService(db=session)
    await service.create_transactions_from_classified_rows(
        user_id=uuid.UUID(str(payload["user_id"])),
        account_id=uuid.UUID(str(payload["account_id"])),
        account_kind=payload["account_kind"],
        rows=payload.get("rows", []),
        source="bulk_import",
    )
