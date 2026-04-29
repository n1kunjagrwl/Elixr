"""
Service-layer tests for the fx domain.

All external dependencies (DB session, repository, exchangerate client) are mocked.
No real database or network connections are made.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ── Helpers ────────────────────────────────────────────────────────────────────


def _make_service(mock_db: AsyncMock):
    from elixir.domains.fx.services import FXService

    return FXService(db=mock_db)


def _make_fx_rate(
    from_currency: str = "USD",
    to_currency: str = "INR",
    rate: Decimal = Decimal("83.500000"),
    fetched_at: datetime | None = None,
    rate_id: uuid.UUID | None = None,
) -> MagicMock:
    if fetched_at is None:
        fetched_at = datetime.now(timezone.utc)
    r = MagicMock()
    r.id = rate_id or uuid.uuid4()
    r.from_currency = from_currency
    r.to_currency = to_currency
    r.rate = rate
    r.fetched_at = fetched_at
    r.created_at = fetched_at
    return r


# ── convert() tests ────────────────────────────────────────────────────────────


class TestConvertSameCurrency:
    async def test_convert_same_currency_returns_amount_unchanged(
        self, mock_db: AsyncMock
    ):
        """convert(100, 'INR', 'INR') must return 100 without touching the DB."""
        svc = _make_service(mock_db)

        with patch.object(svc._repo, "get_rate", new=AsyncMock()) as mock_get_rate:
            result = await svc.convert(Decimal("100.00"), "INR", "INR")

        assert result == Decimal("100.00")
        mock_get_rate.assert_not_called()

    async def test_convert_same_non_inr_currency_returns_amount_unchanged(
        self, mock_db: AsyncMock
    ):
        """convert(50, 'USD', 'USD') must return 50 without touching the DB."""
        svc = _make_service(mock_db)

        with patch.object(svc._repo, "get_rate", new=AsyncMock()) as mock_get_rate:
            result = await svc.convert(Decimal("50.00"), "USD", "USD")

        assert result == Decimal("50.00")
        mock_get_rate.assert_not_called()


class TestConvertUSDToINR:
    async def test_convert_usd_to_inr_returns_correct_amount(self, mock_db: AsyncMock):
        """100 USD * 83.5 INR/USD = 8350 INR."""
        svc = _make_service(mock_db)
        rate = _make_fx_rate("USD", "INR", Decimal("83.500000"))

        with patch.object(svc._repo, "get_rate", new=AsyncMock(return_value=rate)):
            result = await svc.convert(Decimal("100.00"), "USD", "INR")

        assert result == Decimal("100.00") * Decimal("83.500000")

    async def test_convert_inr_to_usd_returns_correct_amount(self, mock_db: AsyncMock):
        """8350 INR / 83.5 = 100 USD. Rate stored as USD→INR, so INR→USD = amount / rate."""
        svc = _make_service(mock_db)
        # For INR→USD, we look up USD→INR rate and divide
        rate = _make_fx_rate("USD", "INR", Decimal("83.500000"))

        with patch.object(svc._repo, "get_rate", new=AsyncMock(return_value=rate)):
            result = await svc.convert(Decimal("8350.00"), "INR", "USD")

        expected = Decimal("8350.00") / Decimal("83.500000")
        assert abs(result - expected) < Decimal("0.000001")


class TestConvertTriangulation:
    async def test_convert_triangulates_non_inr_pair(self, mock_db: AsyncMock):
        """USD→EUR via INR: amount_eur = amount_usd * (USD→INR) / (EUR→INR)."""
        svc = _make_service(mock_db)
        usd_inr = _make_fx_rate("USD", "INR", Decimal("83.500000"))
        eur_inr = _make_fx_rate("EUR", "INR", Decimal("91.000000"))

        async def mock_get_rate(from_currency: str, to_currency: str):
            if from_currency == "USD" and to_currency == "INR":
                return usd_inr
            if from_currency == "EUR" and to_currency == "INR":
                return eur_inr
            return None

        with patch.object(svc._repo, "get_rate", new=mock_get_rate):
            result = await svc.convert(Decimal("100.00"), "USD", "EUR")

        expected = Decimal("100.00") * Decimal("83.500000") / Decimal("91.000000")
        assert abs(result - expected) < Decimal("0.000001")


class TestConvertMissingRate:
    async def test_convert_missing_rate_raises_fx_rate_unavailable(
        self, mock_db: AsyncMock
    ):
        """When no rate row exists, FXRateUnavailableError must be raised."""
        from elixir.shared.exceptions import FXRateUnavailableError

        svc = _make_service(mock_db)

        with patch.object(svc._repo, "get_rate", new=AsyncMock(return_value=None)):
            with pytest.raises(FXRateUnavailableError):
                await svc.convert(Decimal("100.00"), "USD", "INR")

    async def test_convert_missing_from_rate_during_triangulation_raises_fx_rate_unavailable(
        self, mock_db: AsyncMock
    ):
        """If USD→INR is missing during USD→EUR triangulation, raise FXRateUnavailableError."""
        from elixir.shared.exceptions import FXRateUnavailableError

        svc = _make_service(mock_db)
        eur_inr = _make_fx_rate("EUR", "INR", Decimal("91.000000"))

        async def mock_get_rate(from_currency: str, to_currency: str):
            if from_currency == "EUR" and to_currency == "INR":
                return eur_inr
            return None

        with patch.object(svc._repo, "get_rate", new=mock_get_rate):
            with pytest.raises(FXRateUnavailableError):
                await svc.convert(Decimal("100.00"), "USD", "EUR")


class TestConvertStaleRate:
    async def test_convert_stale_rate_logs_warning(self, mock_db: AsyncMock, caplog):
        """When rate is >24h old and as_of_date is None, log a warning (do not raise)."""
        import logging

        svc = _make_service(mock_db)
        stale_fetched_at = datetime.now(timezone.utc) - timedelta(hours=25)
        rate = _make_fx_rate(
            "USD", "INR", Decimal("83.500000"), fetched_at=stale_fetched_at
        )

        with patch.object(svc._repo, "get_rate", new=AsyncMock(return_value=rate)):
            with caplog.at_level(logging.WARNING, logger="elixir.domains.fx.services"):
                result = await svc.convert(Decimal("100.00"), "USD", "INR")

        # Must not raise — stale rate is used with just a warning
        assert result == Decimal("100.00") * Decimal("83.500000")
        assert any("stale" in record.message.lower() for record in caplog.records)

    async def test_convert_stale_rate_with_as_of_date_does_not_warn(
        self, mock_db: AsyncMock, caplog
    ):
        """When as_of_date is provided, staleness warning is suppressed."""
        import logging

        svc = _make_service(mock_db)
        stale_fetched_at = datetime.now(timezone.utc) - timedelta(hours=25)
        rate = _make_fx_rate(
            "USD", "INR", Decimal("83.500000"), fetched_at=stale_fetched_at
        )

        with patch.object(svc._repo, "get_rate", new=AsyncMock(return_value=rate)):
            with caplog.at_level(logging.WARNING, logger="elixir.domains.fx.services"):
                result = await svc.convert(
                    Decimal("100.00"),
                    "USD",
                    "INR",
                    as_of_date=datetime.now(timezone.utc).date(),
                )

        assert result == Decimal("100.00") * Decimal("83.500000")
        # No stale warning when as_of_date is explicitly given
        assert not any("stale" in record.message.lower() for record in caplog.records)


# ── refresh_rates() tests ──────────────────────────────────────────────────────


class TestRefreshRates:
    async def test_refresh_rates_upserts_rates(self, mock_db: AsyncMock):
        """refresh_rates() calls upsert_rate for each currency fetched."""
        svc = _make_service(mock_db)
        upserted: list[tuple[str, str, Decimal]] = []

        mock_client = AsyncMock()
        mock_client.fetch_rate = AsyncMock(return_value=Decimal("83.500000"))

        async def capture_upsert(from_currency, to_currency, rate, fetched_at):
            upserted.append((from_currency, to_currency, rate))

        with patch.object(svc._repo, "upsert_rate", new=capture_upsert):
            await svc.refresh_rates(["USD", "EUR"], mock_client)

        assert len(upserted) == 2
        currencies_fetched = {entry[0] for entry in upserted}
        assert "USD" in currencies_fetched
        assert "EUR" in currencies_fetched
        # All rates stored as X→INR
        assert all(entry[1] == "INR" for entry in upserted)

    async def test_refresh_rates_idempotent(self, mock_db: AsyncMock):
        """Calling refresh_rates twice upserts twice — idempotent, no duplicates from double-call."""
        svc = _make_service(mock_db)
        upserted: list[tuple[str, str, Decimal]] = []

        mock_client = AsyncMock()
        mock_client.fetch_rate = AsyncMock(return_value=Decimal("83.500000"))

        async def capture_upsert(from_currency, to_currency, rate, fetched_at):
            upserted.append((from_currency, to_currency, rate))

        with patch.object(svc._repo, "upsert_rate", new=capture_upsert):
            await svc.refresh_rates(["USD"], mock_client)
            await svc.refresh_rates(["USD"], mock_client)

        # Called twice total — but idempotency is guaranteed by the DB upsert (ON CONFLICT DO UPDATE)
        assert len(upserted) == 2
        assert all(entry[1] == "INR" for entry in upserted)


# ── list_rates() tests ─────────────────────────────────────────────────────────


class TestListRates:
    async def test_list_rates_returns_all_rates(self, mock_db: AsyncMock):
        """list_rates() delegates to the repository and returns FXRate objects."""
        svc = _make_service(mock_db)
        rates = [
            _make_fx_rate("USD", "INR", Decimal("83.5")),
            _make_fx_rate("EUR", "INR", Decimal("91.0")),
        ]

        with patch.object(
            svc._repo, "list_all_rates", new=AsyncMock(return_value=rates)
        ):
            result = await svc.list_rates()

        assert len(result) == 2

    async def test_list_rates_empty_returns_empty_list(self, mock_db: AsyncMock):
        """When no rates exist, list_rates() returns an empty list."""
        svc = _make_service(mock_db)

        with patch.object(svc._repo, "list_all_rates", new=AsyncMock(return_value=[])):
            result = await svc.list_rates()

        assert result == []
