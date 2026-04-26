import uuid
from datetime import date
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from elixir.domains.earnings.models import Earning, EarningsOutbox, EarningSource


class EarningsRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def create_source(
        self,
        user_id: uuid.UUID,
        name: str,
        source_type: str,
    ) -> EarningSource:
        source = EarningSource(user_id=user_id, name=name, type=source_type)
        self._db.add(source)
        await self._db.flush()
        return source

    async def list_sources(
        self,
        user_id: uuid.UUID,
        active_only: bool = False,
    ) -> list[EarningSource]:
        query = select(EarningSource).where(EarningSource.user_id == user_id)
        if active_only:
            query = query.where(EarningSource.is_active.is_(True))
        query = query.order_by(EarningSource.name.asc())
        result = await self._db.execute(query)
        return list(result.scalars().all())

    async def get_source(
        self,
        user_id: uuid.UUID,
        source_id: uuid.UUID,
    ) -> EarningSource | None:
        result = await self._db.execute(
            select(EarningSource).where(
                EarningSource.id == source_id,
                EarningSource.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    async def update_source(self, source: EarningSource, **fields: Any) -> None:
        for key, value in fields.items():
            setattr(source, key, value)
        source.updated_at = datetime.now(timezone.utc)

    async def create_earning(self, **fields: Any) -> Earning:
        earning = Earning(**fields)
        self._db.add(earning)
        await self._db.flush()
        return earning

    async def get_earning(
        self,
        user_id: uuid.UUID,
        earning_id: uuid.UUID,
    ) -> Earning | None:
        result = await self._db.execute(
            select(Earning).where(
                Earning.id == earning_id,
                Earning.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_earning_by_transaction(
        self,
        user_id: uuid.UUID,
        transaction_id: uuid.UUID,
    ) -> Earning | None:
        result = await self._db.execute(
            select(Earning).where(
                Earning.user_id == user_id,
                Earning.transaction_id == transaction_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_earnings(
        self,
        user_id: uuid.UUID,
        source_type: str | None = None,
        date_from: Any | None = None,
        date_to: Any | None = None,
        source_id: uuid.UUID | None = None,
    ) -> list[Earning]:
        query = select(Earning).where(Earning.user_id == user_id)
        if source_type is not None:
            query = query.where(Earning.source_type == source_type)
        if date_from is not None:
            query = query.where(Earning.date >= date_from)
        if date_to is not None:
            query = query.where(Earning.date <= date_to)
        if source_id is not None:
            query = query.where(Earning.source_id == source_id)
        query = query.order_by(Earning.date.desc(), Earning.created_at.desc())
        result = await self._db.execute(query)
        return list(result.scalars().all())

    async def update_earning(self, earning: Earning, **fields: Any) -> None:
        for key, value in fields.items():
            setattr(earning, key, value)
        earning.updated_at = datetime.now(timezone.utc)

    async def list_peer_contact_names(self, user_id: uuid.UUID) -> list[str]:
        result = await self._db.execute(
            text(
                "SELECT name FROM peer_contacts_public "
                "WHERE user_id = :user_id"
            ),
            {"user_id": str(user_id)},
        )
        return [str(row[0]) for row in result.fetchall()]

    async def get_transaction_snapshot(
        self,
        user_id: uuid.UUID,
        transaction_id: uuid.UUID,
    ) -> dict[str, Any] | None:
        result = await self._db.execute(
            text(
                "SELECT "
                "id, user_id, amount, currency, date, type, source, raw_description "
                "FROM transactions_with_categories "
                "WHERE user_id = :user_id AND id = :transaction_id "
                "ORDER BY is_primary DESC, item_id "
                "LIMIT 1"
            ),
            {
                "user_id": str(user_id),
                "transaction_id": str(transaction_id),
            },
        )
        row = result.mappings().first()
        if row is None:
            return None

        snapshot = dict(row)
        snapshot["id"] = uuid.UUID(str(snapshot["id"]))
        snapshot["user_id"] = uuid.UUID(str(snapshot["user_id"]))
        if not isinstance(snapshot["date"], date):
            snapshot["date"] = date.fromisoformat(str(snapshot["date"]))
        return snapshot

    async def find_recurring_source_match(
        self,
        user_id: uuid.UUID,
        amount: Any,
        earning_date: date,
    ) -> EarningSource | None:
        result = await self._db.execute(
            text(
                "SELECT es.id, es.user_id, es.name, es.type, es.is_active, "
                "es.created_at, es.updated_at, COUNT(e.id) AS match_count "
                "FROM earning_sources es "
                "JOIN earnings e ON e.source_id = es.id "
                "WHERE es.user_id = :user_id "
                "  AND es.is_active = true "
                "  AND e.user_id = :user_id "
                "  AND e.amount BETWEEN :amount_min AND :amount_max "
                "  AND ABS(EXTRACT(DAY FROM e.date) - :day_of_month) <= 3 "
                "GROUP BY es.id, es.user_id, es.name, es.type, es.is_active, es.created_at, es.updated_at "
                "ORDER BY match_count DESC, es.created_at ASC "
                "LIMIT 1"
            ),
            {
                "user_id": str(user_id),
                "amount_min": amount * 0.95,
                "amount_max": amount * 1.05,
                "day_of_month": earning_date.day,
            },
        )
        row = result.mappings().first()
        if row is None:
            return None

        source = EarningSource(
            id=uuid.UUID(str(row["id"])),
            user_id=uuid.UUID(str(row["user_id"])),
            name=str(row["name"]),
            type=str(row["type"]),
            is_active=bool(row["is_active"]),
        )
        source.created_at = row["created_at"]
        source.updated_at = row["updated_at"]
        return source

    async def add_outbox_event(
        self, event_type: str, payload: dict[str, Any]
    ) -> None:
        row = EarningsOutbox(event_type=event_type, payload=payload)
        self._db.add(row)
