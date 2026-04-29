"""
Service-layer tests for the investments domain.

All external dependencies (DB session, repository) are mocked.
No real database or network connections are made.
"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tests.conftest import USER_ID


# ── Helpers ────────────────────────────────────────────────────────────────────


def _make_service(mock_db):
    from elixir.domains.investments.services import InvestmentsService

    return InvestmentsService(db=mock_db)


def _make_instrument(
    instrument_id=None,
    name="Reliance Industries",
    ticker="RELIANCE",
    isin="INE002A01018",
    type_="stock",
    exchange="NSE",
    currency="INR",
    data_source="eodhd",
):
    inst = MagicMock()
    inst.id = instrument_id or uuid.uuid4()
    inst.name = name
    inst.ticker = ticker
    inst.isin = isin
    inst.type = type_
    inst.exchange = exchange
    inst.currency = currency
    inst.data_source = data_source
    inst.govt_rate_percent = None
    inst.created_at = None
    inst.updated_at = None
    return inst


def _make_holding(
    holding_id=None,
    user_id=None,
    instrument_id=None,
    units=Decimal("10.000000"),
    avg_cost_per_unit=Decimal("2500.0000"),
    total_invested=Decimal("25000.00"),
    current_value=Decimal("27000.00"),
    current_price=Decimal("2700.0000"),
):
    h = MagicMock()
    h.id = holding_id or uuid.uuid4()
    h.user_id = user_id or USER_ID
    h.instrument_id = instrument_id or uuid.uuid4()
    h.units = units
    h.avg_cost_per_unit = avg_cost_per_unit
    h.total_invested = total_invested
    h.current_value = current_value
    h.current_price = current_price
    h.last_valued_at = None
    h.created_at = None
    h.updated_at = None
    return h


def _make_sip(
    sip_id=None,
    user_id=None,
    instrument_id=None,
    amount=Decimal("5000.00"),
    frequency="monthly",
    debit_day=5,
    bank_account_id=None,
    is_active=True,
):
    s = MagicMock()
    s.id = sip_id or uuid.uuid4()
    s.user_id = user_id or USER_ID
    s.instrument_id = instrument_id or uuid.uuid4()
    s.amount = amount
    s.frequency = frequency
    s.debit_day = debit_day
    s.bank_account_id = bank_account_id or uuid.uuid4()
    s.is_active = is_active
    s.created_at = None
    s.updated_at = None
    return s


def _make_fd_details(
    fd_id=None,
    holding_id=None,
    principal=Decimal("100000.00"),
    rate_percent=Decimal("7.000"),
    tenure_days=365,
    start_date=date(2024, 1, 1),
    maturity_date=date(2025, 1, 1),
    compounding="quarterly",
    maturity_amount=None,
):
    fd = MagicMock()
    fd.id = fd_id or uuid.uuid4()
    fd.holding_id = holding_id or uuid.uuid4()
    fd.principal = principal
    fd.rate_percent = rate_percent
    fd.tenure_days = tenure_days
    fd.start_date = start_date
    fd.maturity_date = maturity_date
    fd.compounding = compounding
    fd.maturity_amount = maturity_amount
    fd.created_at = None
    return fd


# ── search_instruments tests ──────────────────────────────────────────────────


class TestSearchInstruments:
    async def test_search_instruments_returns_matching(self, mock_db):
        """search_instruments returns instruments matching the query."""

        svc = _make_service(mock_db)
        inst = _make_instrument()

        with patch.object(
            svc._repo, "search_instruments", new=AsyncMock(return_value=[inst])
        ):
            results = await svc.search_instruments(q="Reliance", type_filter=None)

        assert len(results) == 1
        assert results[0].name == "Reliance Industries"

    async def test_search_instruments_with_type_filter(self, mock_db):
        """search_instruments passes type_filter to repo."""
        svc = _make_service(mock_db)
        inst = _make_instrument(type_="mf", name="HDFC Equity Fund")

        with patch.object(
            svc._repo, "search_instruments", new=AsyncMock(return_value=[inst])
        ) as mock_search:
            results = await svc.search_instruments(q="HDFC", type_filter="mf")

        mock_search.assert_called_once_with(q="HDFC", type_filter="mf")
        assert len(results) == 1


# ── create_instrument tests ───────────────────────────────────────────────────


class TestCreateInstrument:
    async def test_create_instrument_creates_row(self, mock_db):
        """create_instrument persists a new instrument."""
        from elixir.domains.investments.schemas import InstrumentCreate

        svc = _make_service(mock_db)
        inst = _make_instrument()

        data = InstrumentCreate(
            name="Reliance Industries",
            type="stock",
            currency="INR",
        )

        with patch.object(
            svc._repo, "create_instrument", new=AsyncMock(return_value=inst)
        ):
            result = await svc.create_instrument(data)

        assert result.name == "Reliance Industries"
        mock_db.commit.assert_called_once()


# ── list_holdings tests ───────────────────────────────────────────────────────


class TestListHoldings:
    async def test_list_holdings_returns_user_holdings(self, mock_db):
        """list_holdings returns all holdings for the user."""
        svc = _make_service(mock_db)
        h1 = _make_holding()
        h2 = _make_holding()

        with patch.object(
            svc._repo, "list_holdings", new=AsyncMock(return_value=[h1, h2])
        ):
            results = await svc.list_holdings(USER_ID)

        assert len(results) == 2


# ── add_holding tests ─────────────────────────────────────────────────────────


class TestAddHolding:
    async def test_add_holding_creates_holding(self, mock_db):
        """Happy path: add_holding creates a new holding."""
        from elixir.domains.investments.schemas import HoldingCreate

        svc = _make_service(mock_db)
        inst = _make_instrument()
        holding = _make_holding(instrument_id=inst.id)

        data = HoldingCreate(
            instrument_id=inst.id,
            units=Decimal("10"),
            avg_cost_per_unit=Decimal("2500"),
        )

        with (
            patch.object(svc._repo, "get_instrument", new=AsyncMock(return_value=inst)),
            patch.object(
                svc._repo, "get_holding_by_instrument", new=AsyncMock(return_value=None)
            ),
            patch.object(
                svc._repo, "create_holding", new=AsyncMock(return_value=holding)
            ),
        ):
            result = await svc.add_holding(USER_ID, data)

        assert result is not None
        mock_db.commit.assert_called_once()

    async def test_add_holding_duplicate_instrument_raises_409(self, mock_db):
        """Adding a holding for an already-held instrument raises DuplicateHoldingError."""
        from elixir.domains.investments.schemas import HoldingCreate
        from elixir.shared.exceptions import DuplicateHoldingError

        svc = _make_service(mock_db)
        inst = _make_instrument()
        existing_holding = _make_holding(instrument_id=inst.id)

        data = HoldingCreate(instrument_id=inst.id)

        with (
            patch.object(svc._repo, "get_instrument", new=AsyncMock(return_value=inst)),
            patch.object(
                svc._repo,
                "get_holding_by_instrument",
                new=AsyncMock(return_value=existing_holding),
            ),
        ):
            with pytest.raises(DuplicateHoldingError):
                await svc.add_holding(USER_ID, data)

    async def test_add_holding_instrument_not_found_raises_404(self, mock_db):
        """Adding a holding for a non-existent instrument raises InstrumentNotFoundError."""
        from elixir.domains.investments.schemas import HoldingCreate
        from elixir.shared.exceptions import InstrumentNotFoundError

        svc = _make_service(mock_db)
        data = HoldingCreate(instrument_id=uuid.uuid4())

        with patch.object(
            svc._repo, "get_instrument", new=AsyncMock(return_value=None)
        ):
            with pytest.raises(InstrumentNotFoundError):
                await svc.add_holding(USER_ID, data)


# ── edit_holding tests ────────────────────────────────────────────────────────


class TestEditHolding:
    async def test_edit_holding_updates_fields(self, mock_db):
        """edit_holding updates specified fields on the holding."""
        from elixir.domains.investments.schemas import HoldingUpdate

        svc = _make_service(mock_db)
        holding = _make_holding()
        holding_id = holding.id

        data = HoldingUpdate(units=Decimal("15"), avg_cost_per_unit=Decimal("2600"))

        with (
            patch.object(svc._repo, "get_holding", new=AsyncMock(return_value=holding)),
            patch.object(svc._repo, "update_holding", new=AsyncMock(return_value=None)),
        ):
            result = await svc.edit_holding(USER_ID, holding_id, data)

        assert result is not None
        mock_db.commit.assert_called_once()

    async def test_edit_holding_not_found_raises_404(self, mock_db):
        """edit_holding raises HoldingNotFoundError when holding does not exist."""
        from elixir.domains.investments.schemas import HoldingUpdate
        from elixir.shared.exceptions import HoldingNotFoundError

        svc = _make_service(mock_db)

        with patch.object(svc._repo, "get_holding", new=AsyncMock(return_value=None)):
            with pytest.raises(HoldingNotFoundError):
                await svc.edit_holding(USER_ID, uuid.uuid4(), HoldingUpdate())


# ── remove_holding tests ──────────────────────────────────────────────────────


class TestRemoveHolding:
    async def test_remove_holding_deletes_holding(self, mock_db):
        """remove_holding deletes the specified holding."""
        svc = _make_service(mock_db)
        holding = _make_holding()

        with (
            patch.object(svc._repo, "get_holding", new=AsyncMock(return_value=holding)),
            patch.object(svc._repo, "delete_holding", new=AsyncMock(return_value=None)),
        ):
            await svc.remove_holding(USER_ID, holding.id)

        mock_db.commit.assert_called_once()

    async def test_remove_holding_not_found_raises_404(self, mock_db):
        """remove_holding raises HoldingNotFoundError when holding does not exist."""
        from elixir.shared.exceptions import HoldingNotFoundError

        svc = _make_service(mock_db)

        with patch.object(svc._repo, "get_holding", new=AsyncMock(return_value=None)):
            with pytest.raises(HoldingNotFoundError):
                await svc.remove_holding(USER_ID, uuid.uuid4())


# ── add_fd_details tests ──────────────────────────────────────────────────────


class TestAddFDDetails:
    async def test_add_fd_details_computes_maturity_amount(self, mock_db):
        """add_fd_details computes the maturity_amount server-side."""
        from elixir.domains.investments.schemas import FDDetailsCreate

        svc = _make_service(mock_db)
        holding = _make_holding()
        holding.instrument_id = uuid.uuid4()
        inst = _make_instrument(type_="fd")
        fd = _make_fd_details(holding_id=holding.id, compounding="quarterly")

        data = FDDetailsCreate(
            principal=Decimal("100000"),
            rate_percent=Decimal("7.000"),
            tenure_days=365,
            start_date=date(2024, 1, 1),
            maturity_date=date(2025, 1, 1),
            compounding="quarterly",
        )

        create_fd_mock = AsyncMock(return_value=fd)

        with (
            patch.object(svc._repo, "get_holding", new=AsyncMock(return_value=holding)),
            patch.object(svc._repo, "get_instrument", new=AsyncMock(return_value=inst)),
            patch.object(svc._repo, "get_fd_details", new=AsyncMock(return_value=None)),
            patch.object(svc._repo, "create_fd_details", new=create_fd_mock),
        ):
            result = await svc.add_fd_details(USER_ID, holding.id, data)

        # verify create_fd_details was called with a computed maturity_amount
        call_kwargs = create_fd_mock.call_args
        maturity_amount = call_kwargs.kwargs.get("maturity_amount")
        # The maturity amount for P=100000, r=7%, n=4 (quarterly), t=1 year should be approx 107185.9
        assert maturity_amount is not None
        assert maturity_amount > Decimal("107000")
        assert result is not None
        mock_db.commit.assert_called_once()

    async def test_add_fd_details_non_fd_holding_raises_422(self, mock_db):
        """Adding FD details to a non-FD holding raises FDDetailsRequiredError."""
        from elixir.domains.investments.schemas import FDDetailsCreate
        from elixir.shared.exceptions import FDDetailsRequiredError

        svc = _make_service(mock_db)
        holding = _make_holding()
        inst = _make_instrument(type_="stock")  # not FD

        data = FDDetailsCreate(
            principal=Decimal("100000"),
            rate_percent=Decimal("7.000"),
            tenure_days=365,
            start_date=date(2024, 1, 1),
            maturity_date=date(2025, 1, 1),
            compounding="quarterly",
        )

        with (
            patch.object(svc._repo, "get_holding", new=AsyncMock(return_value=holding)),
            patch.object(svc._repo, "get_instrument", new=AsyncMock(return_value=inst)),
        ):
            with pytest.raises(FDDetailsRequiredError):
                await svc.add_fd_details(USER_ID, holding.id, data)

    async def test_add_fd_details_already_exists_raises_409(self, mock_db):
        """Adding FD details when they already exist raises FDDetailsAlreadyExistError."""
        from elixir.domains.investments.schemas import FDDetailsCreate
        from elixir.shared.exceptions import FDDetailsAlreadyExistError

        svc = _make_service(mock_db)
        holding = _make_holding()
        inst = _make_instrument(type_="fd")
        existing_fd = _make_fd_details(holding_id=holding.id)

        data = FDDetailsCreate(
            principal=Decimal("100000"),
            rate_percent=Decimal("7.000"),
            tenure_days=365,
            start_date=date(2024, 1, 1),
            maturity_date=date(2025, 1, 1),
            compounding="quarterly",
        )

        with (
            patch.object(svc._repo, "get_holding", new=AsyncMock(return_value=holding)),
            patch.object(svc._repo, "get_instrument", new=AsyncMock(return_value=inst)),
            patch.object(
                svc._repo, "get_fd_details", new=AsyncMock(return_value=existing_fd)
            ),
        ):
            with pytest.raises(FDDetailsAlreadyExistError):
                await svc.add_fd_details(USER_ID, holding.id, data)

    async def test_add_fd_details_holding_not_found_raises_404(self, mock_db):
        """add_fd_details raises HoldingNotFoundError when holding does not exist."""
        from elixir.domains.investments.schemas import FDDetailsCreate
        from elixir.shared.exceptions import HoldingNotFoundError

        svc = _make_service(mock_db)

        data = FDDetailsCreate(
            principal=Decimal("100000"),
            rate_percent=Decimal("7.000"),
            tenure_days=365,
            start_date=date(2024, 1, 1),
            maturity_date=date(2025, 1, 1),
            compounding="quarterly",
        )

        with patch.object(svc._repo, "get_holding", new=AsyncMock(return_value=None)):
            with pytest.raises(HoldingNotFoundError):
                await svc.add_fd_details(USER_ID, uuid.uuid4(), data)


# ── get_portfolio_history tests ───────────────────────────────────────────────


class TestGetPortfolioHistory:
    async def test_get_portfolio_history_returns_snapshots(self, mock_db):
        """get_portfolio_history returns list of valuation snapshots in range."""
        svc = _make_service(mock_db)

        snapshots = [
            {"snapshot_date": "2024-01-01", "total_value": "100000.00"},
            {"snapshot_date": "2024-01-02", "total_value": "101000.00"},
        ]

        with patch.object(
            svc._repo, "list_portfolio_history", new=AsyncMock(return_value=snapshots)
        ):
            results = await svc.get_portfolio_history(
                USER_ID,
                from_date=date(2024, 1, 1),
                to_date=date(2024, 1, 31),
            )

        assert len(results) == 2


# ── register_sip tests ────────────────────────────────────────────────────────


class TestRegisterSIP:
    async def test_register_sip_creates_registration(self, mock_db):
        """register_sip creates a new SIP registration."""
        from elixir.domains.investments.schemas import SIPCreate

        svc = _make_service(mock_db)
        inst = _make_instrument()
        sip = _make_sip(instrument_id=inst.id)
        bank_account_id = uuid.uuid4()

        data = SIPCreate(
            instrument_id=inst.id,
            amount=Decimal("5000"),
            frequency="monthly",
            debit_day=5,
            bank_account_id=bank_account_id,
        )

        with (
            patch.object(svc._repo, "get_instrument", new=AsyncMock(return_value=inst)),
            patch.object(svc._repo, "create_sip", new=AsyncMock(return_value=sip)),
        ):
            result = await svc.register_sip(USER_ID, data)

        assert result is not None
        mock_db.commit.assert_called_once()

    async def test_register_sip_instrument_not_found_raises_404(self, mock_db):
        """register_sip raises InstrumentNotFoundError for unknown instrument."""
        from elixir.domains.investments.schemas import SIPCreate
        from elixir.shared.exceptions import InstrumentNotFoundError

        svc = _make_service(mock_db)

        data = SIPCreate(
            instrument_id=uuid.uuid4(),
            amount=Decimal("5000"),
            frequency="monthly",
        )

        with patch.object(
            svc._repo, "get_instrument", new=AsyncMock(return_value=None)
        ):
            with pytest.raises(InstrumentNotFoundError):
                await svc.register_sip(USER_ID, data)


# ── edit_sip tests ────────────────────────────────────────────────────────────


class TestEditSIP:
    async def test_edit_sip_updates_fields(self, mock_db):
        """edit_sip updates the specified fields on the SIP."""
        from elixir.domains.investments.schemas import SIPUpdate

        svc = _make_service(mock_db)
        sip = _make_sip()

        data = SIPUpdate(amount=Decimal("7500"), debit_day=10)

        with (
            patch.object(svc._repo, "get_sip", new=AsyncMock(return_value=sip)),
            patch.object(svc._repo, "update_sip", new=AsyncMock(return_value=None)),
        ):
            result = await svc.edit_sip(USER_ID, sip.id, data)

        assert result is not None
        mock_db.commit.assert_called_once()

    async def test_edit_sip_not_found_raises_404(self, mock_db):
        """edit_sip raises SIPNotFoundError for unknown SIP."""
        from elixir.domains.investments.schemas import SIPUpdate
        from elixir.shared.exceptions import SIPNotFoundError

        svc = _make_service(mock_db)

        with patch.object(svc._repo, "get_sip", new=AsyncMock(return_value=None)):
            with pytest.raises(SIPNotFoundError):
                await svc.edit_sip(USER_ID, uuid.uuid4(), SIPUpdate())


# ── deactivate_sip tests ──────────────────────────────────────────────────────


class TestDeactivateSIP:
    async def test_deactivate_sip_sets_is_active_false(self, mock_db):
        """deactivate_sip sets is_active to False."""
        svc = _make_service(mock_db)
        sip = _make_sip(is_active=True)

        with (
            patch.object(svc._repo, "get_sip", new=AsyncMock(return_value=sip)),
            patch.object(svc._repo, "deactivate_sip", new=AsyncMock(return_value=None)),
        ):
            await svc.deactivate_sip(USER_ID, sip.id)

        mock_db.commit.assert_called_once()

    async def test_deactivate_sip_not_found_raises_404(self, mock_db):
        """deactivate_sip raises SIPNotFoundError for unknown SIP."""
        from elixir.shared.exceptions import SIPNotFoundError

        svc = _make_service(mock_db)

        with patch.object(svc._repo, "get_sip", new=AsyncMock(return_value=None)):
            with pytest.raises(SIPNotFoundError):
                await svc.deactivate_sip(USER_ID, uuid.uuid4())


# ── confirm_sip_link tests ────────────────────────────────────────────────────


class TestConfirmSIPLink:
    async def test_confirm_sip_link_writes_outbox_event(self, mock_db):
        """confirm_sip_link writes a SIPLinked event to the outbox."""
        svc = _make_service(mock_db)
        sip = _make_sip()
        transaction_id = uuid.uuid4()
        outbox_events = []

        with (
            patch.object(svc._repo, "get_sip", new=AsyncMock(return_value=sip)),
            patch.object(
                svc._repo,
                "add_outbox_event",
                new=AsyncMock(side_effect=lambda et, p: outbox_events.append((et, p))),
            ),
        ):
            await svc.confirm_sip_link(USER_ID, sip.id, transaction_id)

        mock_db.commit.assert_called_once()
        assert len(outbox_events) == 1
        event_type, payload = outbox_events[0]
        assert event_type == "investments.SIPLinked"
        assert payload["sip_registration_id"] == str(sip.id)
        assert payload["transaction_id"] == str(transaction_id)


# ── event handler tests ───────────────────────────────────────────────────────


class TestHandleAccountRemoved:
    async def test_handle_account_removed_deactivates_sips(self, mock_db):
        """handle_account_removed deactivates all SIPs with matching bank_account_id."""
        svc = _make_service(mock_db)
        account_id = uuid.uuid4()

        deactivate_mock = AsyncMock(return_value=None)

        with patch.object(
            svc._repo, "deactivate_sips_for_account", new=deactivate_mock
        ):
            await svc.handle_account_removed(
                {"account_id": str(account_id), "user_id": str(USER_ID)}
            )

        deactivate_mock.assert_called_once_with(account_id)


class TestHandleTransactionCreated:
    def _make_transaction_payload(
        self,
        transaction_id=None,
        user_id=None,
        type_="debit",
        amount="5000.00",
        date_="2024-01-05",
        bank_account_id=None,
    ):
        return {
            "transaction_id": str(transaction_id or uuid.uuid4()),
            "user_id": str(user_id or USER_ID),
            "type": type_,
            "amount": amount,
            "date": date_,
            "bank_account_id": str(bank_account_id or uuid.uuid4()),
        }

    async def test_handle_transaction_created_skips_credits(self, mock_db):
        """Credits are not checked against SIPs."""
        svc = _make_service(mock_db)
        payload = self._make_transaction_payload(type_="credit")

        with patch.object(
            svc._repo, "list_active_sips_for_user", new=AsyncMock(return_value=[])
        ) as mock_list:
            await svc.handle_transaction_created(payload)

        mock_list.assert_not_called()

    async def test_handle_transaction_created_detects_sip_match(self, mock_db):
        """A debit matching a SIP's amount (±2%), date (±3 days), and account writes SIPDetected."""
        svc = _make_service(mock_db)

        bank_account_id = uuid.uuid4()
        sip = _make_sip(
            amount=Decimal("5000.00"),
            debit_day=5,
            bank_account_id=bank_account_id,
        )
        transaction_id = uuid.uuid4()

        # amount within 2% of 5000, date is day 5 of the month → matches
        payload = self._make_transaction_payload(
            transaction_id=transaction_id,
            user_id=USER_ID,
            type_="debit",
            amount="5050.00",  # within 2% of 5000
            date_="2024-01-05",
            bank_account_id=bank_account_id,
        )

        outbox_events = []

        with (
            patch.object(
                svc._repo,
                "list_active_sips_for_user",
                new=AsyncMock(return_value=[sip]),
            ),
            patch.object(
                svc._repo, "outbox_event_exists", new=AsyncMock(return_value=False)
            ),
            patch.object(
                svc._repo,
                "add_outbox_event",
                new=AsyncMock(side_effect=lambda et, p: outbox_events.append((et, p))),
            ),
        ):
            await svc.handle_transaction_created(payload)

        assert len(outbox_events) == 1
        event_type, event_payload = outbox_events[0]
        assert event_type == "investments.SIPDetected"
        assert event_payload["transaction_id"] == str(transaction_id)
        assert event_payload["sip_registration_id"] == str(sip.id)

    async def test_handle_transaction_created_skips_when_amount_too_different(
        self, mock_db
    ):
        """A debit more than 2% different from SIP amount is not detected."""
        svc = _make_service(mock_db)

        bank_account_id = uuid.uuid4()
        sip = _make_sip(
            amount=Decimal("5000.00"),
            debit_day=5,
            bank_account_id=bank_account_id,
        )

        # amount is 10% more — outside 2% threshold
        payload = self._make_transaction_payload(
            type_="debit",
            amount="5500.00",
            date_="2024-01-05",
            bank_account_id=bank_account_id,
        )

        outbox_events = []

        with (
            patch.object(
                svc._repo,
                "list_active_sips_for_user",
                new=AsyncMock(return_value=[sip]),
            ),
            patch.object(
                svc._repo,
                "add_outbox_event",
                new=AsyncMock(side_effect=lambda et, p: outbox_events.append((et, p))),
            ),
        ):
            await svc.handle_transaction_created(payload)

        assert len(outbox_events) == 0

    async def test_handle_transaction_created_is_idempotent(self, mock_db):
        """SIPDetected is not written again if the outbox row already exists."""
        svc = _make_service(mock_db)

        bank_account_id = uuid.uuid4()
        sip = _make_sip(
            amount=Decimal("5000.00"),
            debit_day=5,
            bank_account_id=bank_account_id,
        )
        transaction_id = uuid.uuid4()

        payload = self._make_transaction_payload(
            transaction_id=transaction_id,
            type_="debit",
            amount="5000.00",
            date_="2024-01-05",
            bank_account_id=bank_account_id,
        )

        outbox_events = []

        with (
            patch.object(
                svc._repo,
                "list_active_sips_for_user",
                new=AsyncMock(return_value=[sip]),
            ),
            patch.object(
                svc._repo, "outbox_event_exists", new=AsyncMock(return_value=True)
            ),
            patch.object(
                svc._repo,
                "add_outbox_event",
                new=AsyncMock(side_effect=lambda et, p: outbox_events.append((et, p))),
            ),
        ):
            await svc.handle_transaction_created(payload)

        # idempotent — no new outbox row written
        assert len(outbox_events) == 0


# ── compute_maturity_amount tests ─────────────────────────────────────────────


class TestComputeMaturityAmount:
    def test_compute_maturity_amount_quarterly(self):
        """Quarterly compounding formula produces expected result."""
        from elixir.domains.investments.services import compute_maturity_amount

        result = compute_maturity_amount(
            principal=Decimal("100000"),
            rate_percent=Decimal("7"),
            tenure_days=365,
            compounding="quarterly",
        )
        # P*(1 + r/n)^(n*t) = 100000*(1+0.07/4)^(4*1) ≈ 107185.9
        assert result > Decimal("107000")
        assert result < Decimal("107500")

    def test_compute_maturity_amount_simple(self):
        """Simple interest formula: P*(1 + r*t)."""
        from elixir.domains.investments.services import compute_maturity_amount

        result = compute_maturity_amount(
            principal=Decimal("100000"),
            rate_percent=Decimal("7"),
            tenure_days=365,
            compounding="simple",
        )
        # P*(1 + r*t) = 100000*(1 + 0.07*1) = 107000
        assert result == pytest.approx(Decimal("107000"), rel=Decimal("0.001"))

    def test_compute_maturity_amount_annually(self):
        """Annual compounding formula."""
        from elixir.domains.investments.services import compute_maturity_amount

        result = compute_maturity_amount(
            principal=Decimal("100000"),
            rate_percent=Decimal("7"),
            tenure_days=365,
            compounding="annually",
        )
        # P*(1 + r)^t = 100000*1.07 = 107000
        assert result > Decimal("106900")
        assert result < Decimal("107100")

    def test_compute_maturity_amount_monthly(self):
        """Monthly compounding produces slightly higher than quarterly."""
        from elixir.domains.investments.services import compute_maturity_amount

        quarterly_result = compute_maturity_amount(
            principal=Decimal("100000"),
            rate_percent=Decimal("7"),
            tenure_days=365,
            compounding="quarterly",
        )
        monthly_result = compute_maturity_amount(
            principal=Decimal("100000"),
            rate_percent=Decimal("7"),
            tenure_days=365,
            compounding="monthly",
        )
        assert monthly_result > quarterly_result
