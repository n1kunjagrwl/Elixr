from datetime import datetime
from decimal import Decimal

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from elixir.domains.fx.models import FXRate


class FXRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_rate(self, from_currency: str, to_currency: str) -> FXRate | None:
        """Return the cached FX rate for the given currency pair, or None."""
        result = await self._db.execute(
            select(FXRate).where(
                FXRate.from_currency == from_currency,
                FXRate.to_currency == to_currency,
            )
        )
        return result.scalar_one_or_none()

    async def upsert_rate(
        self,
        from_currency: str,
        to_currency: str,
        rate: Decimal,
        fetched_at: datetime,
    ) -> None:
        """
        INSERT a rate row, or UPDATE the existing one on conflict.

        Uses PostgreSQL INSERT ... ON CONFLICT DO UPDATE to guarantee idempotency.
        """
        await self._db.execute(
            text(
                """
                INSERT INTO fx_rates (id, from_currency, to_currency, rate, fetched_at, created_at)
                VALUES (gen_random_uuid(), :from_currency, :to_currency, :rate, :fetched_at, now())
                ON CONFLICT (from_currency, to_currency)
                DO UPDATE SET rate = EXCLUDED.rate, fetched_at = EXCLUDED.fetched_at
                """
            ),
            {
                "from_currency": from_currency,
                "to_currency": to_currency,
                "rate": str(rate),
                "fetched_at": fetched_at,
            },
        )
        await self._db.flush()

    async def list_all_rates(self) -> list[FXRate]:
        """Return all cached FX rate rows ordered by from_currency."""
        result = await self._db.execute(
            select(FXRate).order_by(FXRate.from_currency, FXRate.to_currency)
        )
        return list(result.scalars().all())
