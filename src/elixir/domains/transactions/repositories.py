import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from elixir.domains.transactions.models import (
    Transaction,
    TransactionItem,
    TransactionsOutbox,
)
from elixir.shared.pagination import PagedResponse


class TransactionsRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def create_transaction(self, **fields: Any) -> Transaction:
        transaction = Transaction(**fields)
        self._db.add(transaction)
        await self._db.flush()
        return transaction

    async def create_transaction_items(
        self,
        transaction_id: uuid.UUID,
        items: list[dict[str, Any]],
    ) -> list[TransactionItem]:
        created: list[TransactionItem] = []
        for index, item in enumerate(items):
            row = TransactionItem(
                transaction_id=transaction_id,
                category_id=item["category_id"],
                amount=item["amount"],
                currency=item.get("currency", "INR"),
                label=item.get("label"),
                is_primary=item.get("is_primary", index == 0),
            )
            self._db.add(row)
            created.append(row)
        await self._db.flush()
        return created

    async def get_transaction(
        self, user_id: uuid.UUID, transaction_id: uuid.UUID
    ) -> Transaction | None:
        result = await self._db.execute(
            select(Transaction)
            .options(selectinload(Transaction.items))
            .where(
                Transaction.id == transaction_id,
                Transaction.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_transaction_items(
        self, transaction_id: uuid.UUID
    ) -> list[TransactionItem]:
        result = await self._db.execute(
            select(TransactionItem)
            .where(TransactionItem.transaction_id == transaction_id)
            .order_by(TransactionItem.is_primary.desc(), TransactionItem.id)
        )
        return list(result.scalars().all())

    async def update_transaction(self, transaction: Transaction, **fields: Any) -> None:
        for key, value in fields.items():
            setattr(transaction, key, value)
        transaction.updated_at = datetime.now(timezone.utc)

    async def replace_transaction_items(
        self,
        transaction_id: uuid.UUID,
        items: list[dict[str, Any]],
    ) -> list[TransactionItem]:
        await self._db.execute(
            delete(TransactionItem).where(TransactionItem.transaction_id == transaction_id)
        )
        await self._db.flush()
        return await self.create_transaction_items(transaction_id, items)

    async def fingerprint_exists(self, user_id: uuid.UUID, fingerprint: str) -> bool:
        result = await self._db.execute(
            select(Transaction.id)
            .where(
                Transaction.user_id == user_id,
                Transaction.fingerprint == fingerprint,
            )
            .limit(1)
        )
        return result.scalar_one_or_none() is not None

    async def category_ids_exist(
        self,
        user_id: uuid.UUID,
        category_ids: list[uuid.UUID],
    ) -> bool:
        if not category_ids:
            return False
        result = await self._db.execute(
            text(
                "SELECT COUNT(DISTINCT id) AS count "
                "FROM categories_for_user "
                "WHERE (user_id = :uid OR user_id IS NULL) "
                "AND is_active = true "
                "AND id = ANY(:category_ids)"
            ),
            {
                "uid": str(user_id),
                "category_ids": [str(category_id) for category_id in category_ids],
            },
        )
        count = result.scalar_one()
        return int(count) == len(set(category_ids))

    async def get_self_transfer_category_id(
        self, user_id: uuid.UUID
    ) -> uuid.UUID | None:
        result = await self._db.execute(
            text(
                "SELECT id "
                "FROM categories_for_user "
                "WHERE slug = 'self-transfer' "
                "AND is_active = true "
                "AND (user_id = :uid OR user_id IS NULL) "
                "LIMIT 1"
            ),
            {"uid": str(user_id)},
        )
        value = result.scalar_one_or_none()
        if value is None:
            return None
        return uuid.UUID(str(value))

    async def list_transactions(
        self,
        user_id: uuid.UUID,
        filters: Any,
        page: int,
        page_size: int,
    ) -> PagedResponse[dict[str, Any]]:
        clauses = ["t.user_id = :user_id"]
        params: dict[str, Any] = {"user_id": str(user_id)}

        if filters.date_from is not None:
            clauses.append("t.date >= :date_from")
            params["date_from"] = filters.date_from
        if filters.date_to is not None:
            clauses.append("t.date <= :date_to")
            params["date_to"] = filters.date_to
        if filters.account_id is not None:
            clauses.append("t.account_id = :account_id")
            params["account_id"] = str(filters.account_id)
        if filters.type is not None:
            clauses.append("t.type = :type")
            params["type"] = filters.type
        if filters.source is not None:
            clauses.append("t.source = :source")
            params["source"] = filters.source
        if filters.category_id is not None:
            clauses.append(
                "EXISTS (SELECT 1 FROM transaction_items ti2 "
                "WHERE ti2.transaction_id = t.id AND ti2.category_id = :category_id)"
            )
            params["category_id"] = str(filters.category_id)
        if filters.search_text:
            clauses.append("LOWER(COALESCE(t.raw_description, '')) LIKE :search_text")
            params["search_text"] = f"%{filters.search_text.lower()}%"

        where_sql = " AND ".join(clauses)
        total_result = await self._db.execute(
            text(
                "SELECT COUNT(*) "
                "FROM transactions t "
                f"WHERE {where_sql}"
            ),
            params,
        )
        total = int(total_result.scalar_one())

        params["limit"] = page_size
        params["offset"] = PagedResponse.offset(page, page_size)

        result = await self._db.execute(
            text(
                "SELECT "
                "t.id, t.account_id, t.account_kind, t.amount, t.currency, "
                "t.date, t.type, t.source, t.raw_description, t.notes, "
                "uas.nickname AS account_name, "
                "ti.category_id AS primary_category_id, "
                "cfu.name AS primary_category_name, "
                "cfu.icon AS primary_category_icon, "
                "t.created_at, t.updated_at "
                "FROM transactions t "
                "LEFT JOIN user_accounts_summary uas ON uas.id = t.account_id AND uas.user_id = t.user_id "
                "LEFT JOIN transaction_items ti ON ti.transaction_id = t.id AND ti.is_primary = true "
                "LEFT JOIN categories_for_user cfu "
                "  ON cfu.id = ti.category_id AND (cfu.user_id = t.user_id OR cfu.user_id IS NULL) "
                f"WHERE {where_sql} "
                "ORDER BY t.date DESC, t.created_at DESC "
                "LIMIT :limit OFFSET :offset"
            ),
            params,
        )
        rows = [dict(row) for row in result.mappings().all()]
        return PagedResponse(items=rows, total=total, page=page, page_size=page_size)

    async def get_transactions_by_ids(
        self,
        user_id: uuid.UUID,
        transaction_ids: list[uuid.UUID],
    ) -> list[Transaction]:
        if not transaction_ids:
            return []
        result = await self._db.execute(
            select(Transaction)
            .options(selectinload(Transaction.items))
            .where(
                Transaction.user_id == user_id,
                Transaction.id.in_(transaction_ids),
            )
        )
        return list(result.scalars().all())

    async def find_potential_transfers(
        self,
        user_id: uuid.UUID,
        amount: Decimal,
        currency: str,
        txn_date: date,
        account_id: uuid.UUID,
        txn_type: str,
        exclude_transaction_id: uuid.UUID | None = None,
    ) -> list[Transaction]:
        opposite_type = "credit" if txn_type == "debit" else "debit"
        lower = txn_date - timedelta(days=2)
        upper = txn_date + timedelta(days=2)
        query = (
            select(Transaction)
            .options(selectinload(Transaction.items))
            .where(
                Transaction.user_id == user_id,
                Transaction.account_id != account_id,
                Transaction.amount == amount,
                Transaction.currency == currency,
                Transaction.date >= lower,
                Transaction.date <= upper,
                Transaction.type == opposite_type,
            )
            .order_by(Transaction.date.desc())
        )
        if exclude_transaction_id is not None:
            query = query.where(Transaction.id != exclude_transaction_id)
        result = await self._db.execute(query)
        return list(result.scalars().all())

    async def add_outbox_event(
        self, event_type: str, payload: dict[str, Any]
    ) -> None:
        row = TransactionsOutbox(event_type=event_type, payload=payload)
        self._db.add(row)
