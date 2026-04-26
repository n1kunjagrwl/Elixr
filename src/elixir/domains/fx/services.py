"""
FXService — currency conversion and rate refresh logic.

Design decisions:
- INR is the base currency; all rates stored as X→INR.
- convert() never makes a live API call at request time (rates come from the DB cache).
- Triangulation for non-INR pairs: amount_to = amount_from * (from→INR) / (to→INR).
- Staleness warning (>24h old rate) is a log.warning, NOT a raised exception.
- refresh_rates() is called by a Temporal activity (Pattern 3 — sync return value needed).
"""

import logging
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from elixir.domains.fx.models import FXRate
from elixir.domains.fx.repositories import FXRepository
from elixir.domains.fx.schemas import ConvertResponse
from elixir.shared.exceptions import FXRateUnavailableError

logger = logging.getLogger(__name__)

_STALENESS_THRESHOLD = timedelta(hours=24)


class FXService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._repo = FXRepository(db)

    # ── Public API ─────────────────────────────────────────────────────────────

    async def convert(
        self,
        amount: Decimal,
        from_currency: str,
        to_currency: str,
        as_of_date: date | None = None,
    ) -> Decimal:
        """
        Convert *amount* from *from_currency* to *to_currency*.

        - Same currency: returns amount unchanged (no DB query).
        - X→INR or INR→X: single rate lookup.
        - X→Y (non-INR pair): triangulated via INR.
        - Missing rate: raises FXRateUnavailableError.
        - Stale rate (>24h) and as_of_date is None: logs a warning, still returns result.
        """
        if from_currency == to_currency:
            return amount

        if to_currency == "INR":
            rate_row = await self._get_rate_or_raise(from_currency, "INR")
            self._warn_if_stale(rate_row, as_of_date)
            return amount * rate_row.rate

        if from_currency == "INR":
            rate_row = await self._get_rate_or_raise(to_currency, "INR")
            self._warn_if_stale(rate_row, as_of_date)
            return amount / rate_row.rate

        # Triangulate through INR
        from_inr = await self._get_rate_or_raise(from_currency, "INR")
        to_inr = await self._get_rate_or_raise(to_currency, "INR")
        self._warn_if_stale(from_inr, as_of_date)
        self._warn_if_stale(to_inr, as_of_date)
        return amount * from_inr.rate / to_inr.rate

    async def convert_with_meta(
        self,
        amount: Decimal,
        from_currency: str,
        to_currency: str,
        as_of_date: date | None = None,
    ) -> ConvertResponse:
        """
        Like convert() but returns a ConvertResponse with rate metadata.
        Used by the API layer to build the /fx/convert response.
        """
        if from_currency == to_currency:
            return ConvertResponse(
                from_currency=from_currency,
                to_currency=to_currency,
                original_amount=amount,
                converted_amount=amount,
                rate_used=Decimal("1.000000"),
                fetched_at=datetime.now(timezone.utc),
            )

        if to_currency == "INR":
            rate_row = await self._get_rate_or_raise(from_currency, "INR")
            self._warn_if_stale(rate_row, as_of_date)
            converted = amount * rate_row.rate
            return ConvertResponse(
                from_currency=from_currency,
                to_currency=to_currency,
                original_amount=amount,
                converted_amount=converted,
                rate_used=rate_row.rate,
                fetched_at=rate_row.fetched_at,
            )

        if from_currency == "INR":
            rate_row = await self._get_rate_or_raise(to_currency, "INR")
            self._warn_if_stale(rate_row, as_of_date)
            converted = amount / rate_row.rate
            effective_rate = Decimal("1") / rate_row.rate
            return ConvertResponse(
                from_currency=from_currency,
                to_currency=to_currency,
                original_amount=amount,
                converted_amount=converted,
                rate_used=effective_rate,
                fetched_at=rate_row.fetched_at,
            )

        # Triangulate through INR
        from_inr = await self._get_rate_or_raise(from_currency, "INR")
        to_inr = await self._get_rate_or_raise(to_currency, "INR")
        self._warn_if_stale(from_inr, as_of_date)
        self._warn_if_stale(to_inr, as_of_date)
        effective_rate = from_inr.rate / to_inr.rate
        converted = amount * effective_rate
        # Use the older of the two fetched_at timestamps as the authoritative one
        fetched_at = min(from_inr.fetched_at, to_inr.fetched_at)
        return ConvertResponse(
            from_currency=from_currency,
            to_currency=to_currency,
            original_amount=amount,
            converted_amount=converted,
            rate_used=effective_rate,
            fetched_at=fetched_at,
        )

    async def refresh_rates(
        self,
        currencies_to_fetch: list[str],
        exchangerate_client: Any,
    ) -> None:
        """
        Fetch rates from the external client and upsert them into fx_rates.

        Called by the FXRateRefreshWorkflow Temporal activity.
        All rates stored as {currency}→INR.
        """
        fetched_at = datetime.now(timezone.utc)
        for currency in currencies_to_fetch:
            rate = await exchangerate_client.fetch_rate(currency)
            await self._repo.upsert_rate(
                from_currency=currency,
                to_currency="INR",
                rate=rate,
                fetched_at=fetched_at,
            )

    async def list_rates(self) -> list[FXRate]:
        """Return all cached FX rates (used by the /fx/rates endpoint)."""
        return await self._repo.list_all_rates()

    # ── Private helpers ────────────────────────────────────────────────────────

    async def _get_rate_or_raise(self, from_currency: str, to_currency: str) -> FXRate:
        rate_row = await self._repo.get_rate(from_currency, to_currency)
        if rate_row is None:
            raise FXRateUnavailableError(
                f"No cached rate for {from_currency}→{to_currency}. "
                "Rates are refreshed every 6 hours by the FXRateRefreshWorkflow."
            )
        return rate_row

    def _warn_if_stale(self, rate_row: FXRate, as_of_date: date | None) -> None:
        """Log a warning if the cached rate is older than 24 hours and as_of_date is None."""
        if as_of_date is not None:
            return
        age = datetime.now(timezone.utc) - rate_row.fetched_at
        if age > _STALENESS_THRESHOLD:
            logger.warning(
                "Stale FX rate: %s→%s fetched at %s (%.1f hours ago). "
                "The FXRateRefreshWorkflow may not be running.",
                rate_row.from_currency,
                rate_row.to_currency,
                rate_row.fetched_at.isoformat(),
                age.total_seconds() / 3600,
            )
