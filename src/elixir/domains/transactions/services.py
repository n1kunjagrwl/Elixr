from __future__ import annotations

import hashlib
import uuid
from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from elixir.domains.transactions.events import (
    TransactionCategorized,
    TransactionCreated,
    TransactionUpdated,
)
from elixir.domains.transactions.repositories import TransactionsRepository
from elixir.domains.transactions.schemas import (
    TransactionCreate,
    TransactionFilters,
    TransactionItemResponse,
    TransactionListResponse,
    TransactionResponse,
    TransactionSummary,
    TransactionUpdate,
)
from elixir.shared.config import Settings
from elixir.shared.exceptions import (
    CategoryNotFoundError,
    ItemAmountMismatchError,
    TransactionNotFoundError,
)
from elixir.shared.pagination import PagedResponse


class TransactionsService:
    def __init__(self, db: AsyncSession, settings: Settings | None = None) -> None:
        self._db = db
        self._repo = TransactionsRepository(db)
        self._settings = settings

    async def add_transaction(
        self,
        user_id: uuid.UUID,
        data: TransactionCreate,
    ) -> TransactionResponse:
        items_payload = await self._resolve_items_for_type(
            user_id=user_id,
            txn_type=data.type,
            amount=data.amount,
            currency=data.currency,
            items=[item.model_dump() for item in data.items],
        )
        self._ensure_item_amounts_match(data.amount, items_payload)
        await self._ensure_categories_exist(user_id, items_payload)

        transaction = await self._repo.create_transaction(
            user_id=user_id,
            account_id=data.account_id,
            account_kind=data.account_kind,
            amount=data.amount,
            currency=data.currency,
            date=data.date,
            type=data.type,
            source="manual",
            raw_description=data.raw_description,
            notes=data.notes,
            fingerprint=None,
        )
        items = await self._repo.create_transaction_items(transaction.id, items_payload)
        transaction.items = items

        await self._write_created_and_categorized_events(transaction, items)
        await self._db.commit()
        return self._build_transaction_response(transaction)

    async def edit_transaction(
        self,
        user_id: uuid.UUID,
        transaction_id: uuid.UUID,
        data: TransactionUpdate,
    ) -> TransactionResponse:
        transaction = await self._repo.get_transaction(user_id, transaction_id)
        if transaction is None:
            raise TransactionNotFoundError(f"Transaction {transaction_id} not found.")

        changed_fields: list[str] = []
        update_fields: dict[str, Any] = {}

        if data.notes is not None and data.notes != transaction.notes:
            update_fields["notes"] = data.notes
            changed_fields.append("notes")

        requested_type = data.type if data.type is not None else transaction.type
        if data.type is not None and data.type != transaction.type:
            update_fields["type"] = data.type
            changed_fields.append("type")

        old_items_payload: list[dict] | None = None
        new_items_payload: list[dict] | None = None

        if data.items is not None or requested_type == "transfer":
            if data.items is not None and requested_type != "transfer":
                self._ensure_item_amounts_match(
                    transaction.amount,
                    [item.model_dump() for item in data.items],
                )
            existing_items = await self._repo.get_transaction_items(transaction.id)
            old_items_payload = self._serialize_items_payload(existing_items)

            raw_items = (
                [item.model_dump() for item in data.items]
                if data.items is not None
                else old_items_payload
            )
            resolved_items = await self._resolve_items_for_type(
                user_id=user_id,
                txn_type=requested_type,
                amount=transaction.amount,
                currency=transaction.currency,
                items=raw_items,
            )
            self._ensure_item_amounts_match(transaction.amount, resolved_items)
            await self._ensure_categories_exist(user_id, resolved_items)
            items = await self._repo.replace_transaction_items(transaction.id, resolved_items)
            transaction.items = items
            new_items_payload = self._serialize_items_payload(items)
            changed_fields.append("items")

        if update_fields:
            await self._repo.update_transaction(transaction, **update_fields)

        if changed_fields:
            event = TransactionUpdated(
                transaction_id=transaction.id,
                user_id=user_id,
                date=transaction.date,
                changed_fields=changed_fields,
                old_items=old_items_payload if "items" in changed_fields else None,
                new_items=new_items_payload if "items" in changed_fields else None,
            )
            await self._repo.add_outbox_event(event.event_type, event.to_payload())

        await self._db.commit()
        if update_fields:
            for key, value in update_fields.items():
                setattr(transaction, key, value)
        return self._build_transaction_response(transaction)

    async def list_transactions(
        self,
        user_id: uuid.UUID,
        filters: TransactionFilters,
        page: int = 1,
        page_size: int = 50,
    ) -> TransactionListResponse:
        rows = await self._repo.list_transactions(user_id, filters, page, page_size)
        items = [self._build_transaction_summary(row) for row in rows.items]
        return PagedResponse(items=items, total=rows.total, page=rows.page, page_size=rows.page_size)

    async def get_transaction(
        self,
        user_id: uuid.UUID,
        transaction_id: uuid.UUID,
    ) -> TransactionResponse:
        transaction = await self._repo.get_transaction(user_id, transaction_id)
        if transaction is None:
            raise TransactionNotFoundError(f"Transaction {transaction_id} not found.")
        return self._build_transaction_response(transaction)

    async def create_transactions_from_classified_rows(
        self,
        user_id: uuid.UUID,
        account_id: uuid.UUID,
        account_kind: str,
        rows: list[dict],
        source: str,
    ) -> None:
        new_transaction_ids: list[uuid.UUID] = []

        for row in rows:
            row_date = row["date"]
            description = row.get("description") or row.get("raw_description")
            amount = Decimal(str(row["amount"]))
            fingerprint = self.compute_fingerprint(description, row_date, amount)
            if await self._repo.fingerprint_exists(user_id, fingerprint):
                continue

            txn_type = row["type"]
            currency = row.get("currency", "INR")
            transaction = await self._repo.create_transaction(
                user_id=user_id,
                account_id=account_id,
                account_kind=account_kind,
                amount=amount,
                currency=currency,
                date=row_date,
                type=txn_type,
                source=source,
                raw_description=description,
                notes=row.get("notes"),
                fingerprint=fingerprint,
            )

            items_payload = self._build_import_items_payload(row, currency)
            items = await self._repo.create_transaction_items(transaction.id, items_payload)
            transaction.items = items
            await self._write_created_and_categorized_events(transaction, items)
            new_transaction_ids.append(transaction.id)

        await self._detect_transfers(user_id, new_transaction_ids)
        await self._db.commit()

    async def _detect_transfers(
        self,
        user_id: uuid.UUID,
        new_transaction_ids: list[uuid.UUID],
    ) -> None:
        if not new_transaction_ids:
            return

        transactions = await self._repo.get_transactions_by_ids(user_id, new_transaction_ids)
        transfer_category_id = await self._repo.get_self_transfer_category_id(user_id)
        if transfer_category_id is None:
            return

        for transaction in transactions:
            if transaction.type == "transfer":
                continue
            matches = await self._repo.find_potential_transfers(
                user_id=user_id,
                amount=transaction.amount,
                currency=transaction.currency,
                txn_date=transaction.date,
                account_id=transaction.account_id,
                txn_type=transaction.type,
                exclude_transaction_id=transaction.id,
            )
            if not matches:
                continue

            counterpart = matches[0]
            transfer_items = [
                {
                    "category_id": transfer_category_id,
                    "amount": transaction.amount,
                    "currency": transaction.currency,
                    "label": None,
                    "is_primary": True,
                }
            ]
            await self._repo.update_transaction(transaction, type="transfer")
            await self._repo.update_transaction(counterpart, type="transfer")
            transaction.items = await self._repo.replace_transaction_items(
                transaction.id, transfer_items
            )
            counterpart.items = await self._repo.replace_transaction_items(
                counterpart.id,
                [
                    {
                        "category_id": transfer_category_id,
                        "amount": counterpart.amount,
                        "currency": counterpart.currency,
                        "label": None,
                        "is_primary": True,
                    }
                ],
            )

    async def _write_created_and_categorized_events(
        self,
        transaction: Any,
        items: list[Any],
    ) -> None:
        created_event = TransactionCreated(
            transaction_id=transaction.id,
            user_id=transaction.user_id,
            account_id=transaction.account_id,
            amount=transaction.amount,
            currency=transaction.currency,
            date=transaction.date,
            type=transaction.type,
            source=transaction.source,
            raw_description=transaction.raw_description,
        )
        categorized_event = TransactionCategorized(
            transaction_id=transaction.id,
            user_id=transaction.user_id,
            items=self._serialize_items_payload(items),
        )
        await self._repo.add_outbox_event(created_event.event_type, created_event.to_payload())
        await self._repo.add_outbox_event(
            categorized_event.event_type,
            categorized_event.to_payload(),
        )

    async def _resolve_items_for_type(
        self,
        user_id: uuid.UUID,
        txn_type: str,
        amount: Decimal,
        currency: str,
        items: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        if txn_type != "transfer":
            return self._normalize_items(items, currency)

        transfer_category_id = await self._repo.get_self_transfer_category_id(user_id)
        if transfer_category_id is None:
            raise CategoryNotFoundError("Self Transfer category not found.")
        return [
            {
                "category_id": transfer_category_id,
                "amount": amount,
                "currency": currency,
                "label": None,
                "is_primary": True,
            }
        ]

    async def _ensure_categories_exist(
        self,
        user_id: uuid.UUID,
        items: list[dict[str, Any]],
    ) -> None:
        category_ids = [item["category_id"] for item in items]
        exists = await self._repo.category_ids_exist(user_id, category_ids)
        if not exists:
            raise CategoryNotFoundError("One or more categories are not visible to this user.")

    @staticmethod
    def _normalize_items(
        items: list[dict[str, Any]],
        currency: str,
    ) -> list[dict[str, Any]]:
        normalized: list[dict[str, Any]] = []
        for index, item in enumerate(items):
            normalized.append(
                {
                    "category_id": item["category_id"],
                    "amount": Decimal(str(item["amount"])),
                    "currency": item.get("currency", currency),
                    "label": item.get("label"),
                    "is_primary": item.get("is_primary", index == 0),
                }
            )
        return normalized

    @staticmethod
    def _ensure_item_amounts_match(amount: Decimal, items: list[dict[str, Any]]) -> None:
        total = sum(Decimal(str(item["amount"])) for item in items)
        if total != Decimal(str(amount)):
            raise ItemAmountMismatchError("Item amounts must sum to transaction amount.")

    @staticmethod
    def compute_fingerprint(
        description: str | None,
        txn_date: date,
        amount: Decimal,
    ) -> str:
        normalized = ((description or "").strip().lower() + txn_date.isoformat() + str(amount))
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    def _build_import_items_payload(
        self,
        row: dict[str, Any],
        currency: str,
    ) -> list[dict[str, Any]]:
        if row.get("items"):
            return self._normalize_items(row["items"], currency)
        return self._normalize_items(
            [
                {
                    "category_id": row["category_id"],
                    "amount": row["amount"],
                    "label": row.get("label"),
                }
            ],
            currency,
        )

    def _build_transaction_response(self, transaction: Any) -> TransactionResponse:
        payload = {
            "id": transaction.id,
            "user_id": transaction.user_id,
            "account_id": transaction.account_id,
            "account_kind": transaction.account_kind,
            "amount": transaction.amount,
            "currency": transaction.currency,
            "date": transaction.date,
            "type": transaction.type,
            "source": transaction.source,
            "raw_description": transaction.raw_description,
            "notes": transaction.notes,
            "account_name": self._optional_attr(transaction, "account_name"),
            "items": [self._build_item_response(item) for item in transaction.items],
            "created_at": self._optional_attr(transaction, "created_at"),
            "updated_at": self._optional_attr(transaction, "updated_at"),
        }
        return TransactionResponse(**payload)

    def _build_item_response(self, item: Any) -> TransactionItemResponse:
        payload = {
            "id": item.id,
            "category_id": item.category_id,
            "amount": item.amount,
            "currency": item.currency,
            "label": item.label,
            "is_primary": item.is_primary,
            "updated_at": self._optional_attr(item, "updated_at"),
        }
        return TransactionItemResponse(**payload)

    def _build_transaction_summary(self, row: Any) -> TransactionSummary:
        payload = self._row_to_dict(row)
        return TransactionSummary(**payload)

    @staticmethod
    def _serialize_items_payload(items: list[Any]) -> list[dict[str, Any]]:
        return [
            {
                "category_id": str(item.category_id),
                "amount": str(item.amount),
                "currency": item.currency,
                "label": item.label,
            }
            for item in items
        ]

    @staticmethod
    def _row_to_dict(row: Any) -> dict[str, Any]:
        if isinstance(row, dict):
            return row
        data = {
            key: value
            for key, value in getattr(row, "__dict__", {}).items()
            if not key.startswith("_")
        }
        if data:
            return data
        return {
            "id": row.id,
            "account_id": row.account_id,
            "account_kind": row.account_kind,
            "amount": row.amount,
            "currency": row.currency,
            "date": row.date,
            "type": row.type,
            "source": row.source,
            "raw_description": row.raw_description,
            "notes": row.notes,
        }

    @staticmethod
    def _optional_attr(obj: Any, name: str) -> Any:
        if isinstance(obj, dict):
            return obj.get(name)
        return getattr(obj, "__dict__", {}).get(name)
