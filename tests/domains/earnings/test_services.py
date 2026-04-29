"""
Service-layer tests for the earnings domain.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tests.conftest import USER_ID


def _make_service(mock_db):
    from elixir.domains.earnings.services import EarningsService

    return EarningsService(db=mock_db)


SOURCE_ID = uuid.uuid4()
EARNING_ID = uuid.uuid4()
TRANSACTION_ID = uuid.uuid4()


def _make_source(
    source_id=None,
    user_id=None,
    name="Think41 Salary",
    source_type="salary",
    is_active=True,
):
    source = MagicMock()
    source.id = source_id or SOURCE_ID
    source.user_id = user_id or USER_ID
    source.name = name
    source.type = source_type
    source.is_active = is_active
    source.created_at = datetime.now(timezone.utc)
    source.updated_at = None
    return source


def _make_earning(
    earning_id=None,
    user_id=None,
    transaction_id=None,
    source_id=None,
    source_type="salary",
    source_label="Think41 Salary",
    amount=Decimal("100000.00"),
    currency="INR",
    earning_date=date(2026, 4, 25),
    notes="April salary",
):
    earning = MagicMock()
    earning.id = earning_id or EARNING_ID
    earning.user_id = user_id or USER_ID
    earning.transaction_id = transaction_id
    earning.source_id = source_id
    earning.source_type = source_type
    earning.source_label = source_label
    earning.amount = amount
    earning.currency = currency
    earning.date = earning_date
    earning.notes = notes
    earning.created_at = datetime.now(timezone.utc)
    earning.updated_at = None
    return earning


class TestSourceCrud:
    async def test_list_sources_returns_active_sources(self, mock_db):
        svc = _make_service(mock_db)
        sources = [
            _make_source(),
            _make_source(source_id=uuid.uuid4(), name="Freelance Project"),
        ]
        with patch.object(
            svc._repo, "list_sources", new=AsyncMock(return_value=sources)
        ):
            result = await svc.list_sources(USER_ID)
        assert len(result) == 2
        assert result[0].name == "Think41 Salary"
        assert result[1].name == "Freelance Project"

    async def test_add_source_creates_source(self, mock_db):
        from elixir.domains.earnings.schemas import EarningSourceCreate

        svc = _make_service(mock_db)
        source = _make_source()
        with patch.object(
            svc._repo, "create_source", new=AsyncMock(return_value=source)
        ):
            result = await svc.add_source(
                USER_ID, EarningSourceCreate(name="Think41 Salary", type="salary")
            )
        assert result.name == "Think41 Salary"
        mock_db.commit.assert_called_once()

    async def test_edit_source_updates_fields(self, mock_db):
        from elixir.domains.earnings.schemas import EarningSourceUpdate

        svc = _make_service(mock_db)
        source = _make_source()
        with (
            patch.object(svc._repo, "get_source", new=AsyncMock(return_value=source)),
            patch.object(svc._repo, "update_source", new=AsyncMock(return_value=None)),
        ):
            result = await svc.edit_source(
                USER_ID, SOURCE_ID, EarningSourceUpdate(name="Renamed Source")
            )
        assert result is not None
        mock_db.commit.assert_called_once()

    async def test_deactivate_source_sets_is_active_false(self, mock_db):
        svc = _make_service(mock_db)
        source = _make_source()
        deactivated_fields = {}
        with (
            patch.object(svc._repo, "get_source", new=AsyncMock(return_value=source)),
            patch.object(
                svc._repo,
                "update_source",
                new=AsyncMock(
                    side_effect=lambda s, **fields: deactivated_fields.update(fields)
                ),
            ),
        ):
            await svc.deactivate_source(USER_ID, SOURCE_ID)
        assert deactivated_fields.get("is_active") is False
        mock_db.commit.assert_called_once()

    async def test_deactivate_source_not_found_raises_404(self, mock_db):
        from elixir.shared.exceptions import EarningSourceNotFoundError

        svc = _make_service(mock_db)
        with patch.object(svc._repo, "get_source", new=AsyncMock(return_value=None)):
            with pytest.raises(EarningSourceNotFoundError):
                await svc.deactivate_source(USER_ID, uuid.uuid4())

    async def test_edit_source_not_found_raises_404(self, mock_db):
        from elixir.domains.earnings.schemas import EarningSourceUpdate
        from elixir.shared.exceptions import EarningSourceNotFoundError

        svc = _make_service(mock_db)
        with patch.object(svc._repo, "get_source", new=AsyncMock(return_value=None)):
            with pytest.raises(EarningSourceNotFoundError):
                await svc.edit_source(
                    USER_ID, uuid.uuid4(), EarningSourceUpdate(name="X")
                )


class TestManualEarnings:
    async def test_add_manual_earning_creates_earning_with_no_transaction_id(
        self, mock_db
    ):
        from elixir.domains.earnings.schemas import EarningCreate

        svc = _make_service(mock_db)
        earning = _make_earning(transaction_id=None, source_id=None)
        with (
            patch.object(svc._repo, "get_source", new=AsyncMock(return_value=None)),
            patch.object(
                svc._repo, "create_earning", new=AsyncMock(return_value=earning)
            ),
            patch.object(svc._repo, "add_outbox_event", new=AsyncMock()),
        ):
            result = await svc.add_manual_earning(
                USER_ID,
                EarningCreate(
                    amount=Decimal("100000.00"),
                    currency="INR",
                    date=date(2026, 4, 25),
                    source_type="other",
                ),
            )
        assert result.transaction_id is None

    async def test_add_manual_earning_creates_row_and_outbox_event(self, mock_db):
        from elixir.domains.earnings.schemas import EarningCreate

        svc = _make_service(mock_db)
        earning = _make_earning(transaction_id=None, source_id=SOURCE_ID)
        source = _make_source()
        outbox_events = []
        with (
            patch.object(svc._repo, "get_source", new=AsyncMock(return_value=source)),
            patch.object(
                svc._repo, "create_earning", new=AsyncMock(return_value=earning)
            ),
            patch.object(
                svc._repo,
                "add_outbox_event",
                new=AsyncMock(side_effect=lambda et, p: outbox_events.append((et, p))),
            ),
        ):
            result = await svc.add_manual_earning(
                USER_ID,
                EarningCreate(
                    amount=Decimal("100000.00"),
                    currency="INR",
                    date=date(2026, 4, 25),
                    source_type="salary",
                    source_id=SOURCE_ID,
                ),
            )
        assert result.transaction_id is None
        assert outbox_events[0][0] == "earnings.EarningRecorded"
        mock_db.commit.assert_called_once()

    async def test_edit_earning_updates_fields(self, mock_db):
        from elixir.domains.earnings.schemas import EarningUpdate

        svc = _make_service(mock_db)
        earning = _make_earning()
        with (
            patch.object(svc._repo, "get_earning", new=AsyncMock(return_value=earning)),
            patch.object(svc._repo, "update_earning", new=AsyncMock(return_value=None)),
            patch.object(svc._repo, "get_source", new=AsyncMock(return_value=None)),
        ):
            result = await svc.edit_earning(
                USER_ID, EARNING_ID, EarningUpdate(notes="Updated notes")
            )
        assert result is not None
        mock_db.commit.assert_called_once()

    async def test_edit_earning_not_found_raises_404(self, mock_db):
        from elixir.domains.earnings.schemas import EarningUpdate
        from elixir.shared.exceptions import EarningNotFoundError

        svc = _make_service(mock_db)
        with patch.object(svc._repo, "get_earning", new=AsyncMock(return_value=None)):
            with pytest.raises(EarningNotFoundError):
                await svc.edit_earning(USER_ID, uuid.uuid4(), EarningUpdate(notes="x"))

    async def test_list_earnings_filters(self, mock_db):
        from elixir.domains.earnings.schemas import EarningFilters

        svc = _make_service(mock_db)
        earning = _make_earning()
        with (
            patch.object(
                svc._repo, "list_earnings", new=AsyncMock(return_value=[earning])
            ),
            patch.object(svc._repo, "get_source", new=AsyncMock(return_value=None)),
        ):
            result = await svc.list_earnings(
                USER_ID, EarningFilters(source_type="salary")
            )
        assert len(result) == 1
        assert result[0].source_type == "salary"


class TestClassifyTransaction:
    async def test_classify_transaction_income_creates_earning(self, mock_db):
        from elixir.domains.earnings.schemas import ClassifyTransactionRequest

        svc = _make_service(mock_db)
        earning = _make_earning(transaction_id=TRANSACTION_ID)
        outbox_events = []
        with (
            patch.object(
                svc._repo,
                "get_earning_by_transaction",
                new=AsyncMock(return_value=None),
            ),
            patch.object(
                svc._repo,
                "get_transaction_snapshot",
                new=AsyncMock(
                    return_value={
                        "id": TRANSACTION_ID,
                        "user_id": USER_ID,
                        "amount": Decimal("100000.00"),
                        "currency": "INR",
                        "date": date(2026, 4, 25),
                        "type": "credit",
                        "source": "statement_import",
                        "raw_description": "Think41 Salary",
                    }
                ),
            ),
            patch.object(
                svc._repo, "create_earning", new=AsyncMock(return_value=earning)
            ),
            patch.object(
                svc._repo,
                "add_outbox_event",
                new=AsyncMock(side_effect=lambda et, p: outbox_events.append((et, p))),
            ),
        ):
            await svc.classify_transaction(
                USER_ID,
                TRANSACTION_ID,
                ClassifyTransactionRequest(
                    classification="income",
                    source_type="salary",
                    source_label="Think41 Salary",
                ),
            )
        assert outbox_events[0][0] == "earnings.EarningRecorded"
        mock_db.commit.assert_called_once()

    async def test_classify_transaction_income_twice_raises_409(self, mock_db):
        from elixir.domains.earnings.schemas import ClassifyTransactionRequest
        from elixir.shared.exceptions import TransactionAlreadyClassifiedError

        svc = _make_service(mock_db)
        with patch.object(
            svc._repo,
            "get_earning_by_transaction",
            new=AsyncMock(return_value=_make_earning(transaction_id=TRANSACTION_ID)),
        ):
            with pytest.raises(TransactionAlreadyClassifiedError):
                await svc.classify_transaction(
                    USER_ID,
                    TRANSACTION_ID,
                    ClassifyTransactionRequest(
                        classification="income",
                        source_type="salary",
                        source_label="Think41 Salary",
                    ),
                )

    async def test_classify_transaction_peer_repayment_skips(self, mock_db):
        from elixir.domains.earnings.schemas import ClassifyTransactionRequest

        svc = _make_service(mock_db)
        with (
            patch.object(
                svc._repo,
                "get_earning_by_transaction",
                new=AsyncMock(return_value=None),
            ),
            patch.object(svc._repo, "create_earning", new=AsyncMock()) as mock_create,
        ):
            await svc.classify_transaction(
                USER_ID,
                TRANSACTION_ID,
                ClassifyTransactionRequest(classification="peer_repayment"),
            )
        mock_create.assert_not_called()
        mock_db.commit.assert_not_called()

    async def test_classify_transaction_ignore_noops(self, mock_db):
        from elixir.domains.earnings.schemas import ClassifyTransactionRequest

        svc = _make_service(mock_db)
        with (
            patch.object(
                svc._repo,
                "get_earning_by_transaction",
                new=AsyncMock(return_value=None),
            ),
            patch.object(svc._repo, "create_earning", new=AsyncMock()) as mock_create,
        ):
            await svc.classify_transaction(
                USER_ID,
                TRANSACTION_ID,
                ClassifyTransactionRequest(classification="ignore"),
            )
        mock_create.assert_not_called()
        mock_db.commit.assert_not_called()


class TestTransactionCreatedHandler:
    async def test_handle_transaction_created_skips_debit(self, mock_db):
        svc = _make_service(mock_db)
        with patch.object(svc._repo, "create_earning", new=AsyncMock()) as mock_create:
            await svc.handle_transaction_created(
                {
                    "transaction_id": str(TRANSACTION_ID),
                    "user_id": str(USER_ID),
                    "amount": Decimal("5000.00"),
                    "currency": "INR",
                    "date": "2026-04-25",
                    "type": "debit",
                    "raw_description": "UPI Payment",
                }
            )
        mock_create.assert_not_called()
        mock_db.commit.assert_not_called()

    async def test_handle_transaction_created_skips_transfer(self, mock_db):
        svc = _make_service(mock_db)
        with patch.object(svc._repo, "create_earning", new=AsyncMock()) as mock_create:
            await svc.handle_transaction_created(
                {
                    "transaction_id": str(TRANSACTION_ID),
                    "user_id": str(USER_ID),
                    "amount": Decimal("50000.00"),
                    "currency": "INR",
                    "date": "2026-04-25",
                    "type": "transfer",
                    "raw_description": "NEFT transfer to own account",
                }
            )
        mock_create.assert_not_called()
        mock_db.commit.assert_not_called()

    async def test_transaction_created_salary_keyword_auto_creates_earning(
        self, mock_db
    ):
        svc = _make_service(mock_db)
        outbox_events = []
        earning = _make_earning(transaction_id=TRANSACTION_ID)
        with (
            patch.object(
                svc._repo,
                "get_earning_by_transaction",
                new=AsyncMock(return_value=None),
            ),
            patch.object(
                svc._repo, "list_peer_contact_names", new=AsyncMock(return_value=[])
            ),
            patch.object(svc._repo, "list_sources", new=AsyncMock(return_value=[])),
            patch.object(
                svc._repo,
                "find_recurring_source_match",
                new=AsyncMock(return_value=None),
            ),
            patch.object(
                svc._repo, "create_earning", new=AsyncMock(return_value=earning)
            ),
            patch.object(
                svc._repo,
                "add_outbox_event",
                new=AsyncMock(side_effect=lambda et, p: outbox_events.append((et, p))),
            ),
        ):
            await svc.handle_transaction_created(
                {
                    "transaction_id": str(TRANSACTION_ID),
                    "user_id": str(USER_ID),
                    "amount": Decimal("100000.00"),
                    "currency": "INR",
                    "date": "2026-04-25",
                    "type": "credit",
                    "raw_description": "NEFT SALARY THINK41",
                }
            )
        assert outbox_events[0][0] == "earnings.EarningRecorded"

    async def test_transaction_created_peer_name_skips(self, mock_db):
        svc = _make_service(mock_db)
        with (
            patch.object(
                svc._repo,
                "get_earning_by_transaction",
                new=AsyncMock(return_value=None),
            ),
            patch.object(
                svc._repo,
                "list_peer_contact_names",
                new=AsyncMock(return_value=["Rahul"]),
            ),
            patch.object(svc._repo, "list_sources", new=AsyncMock(return_value=[])),
            patch.object(
                svc._repo,
                "find_recurring_source_match",
                new=AsyncMock(return_value=None),
            ),
            patch.object(svc._repo, "create_earning", new=AsyncMock()) as mock_create,
        ):
            await svc.handle_transaction_created(
                {
                    "transaction_id": str(TRANSACTION_ID),
                    "user_id": str(USER_ID),
                    "amount": Decimal("1500.00"),
                    "currency": "INR",
                    "date": "2026-04-25",
                    "type": "credit",
                    "raw_description": "NEFT Rahul repayment",
                }
            )
        mock_create.assert_not_called()

    async def test_transaction_created_ambiguous_emits_classification_needed(
        self, mock_db
    ):
        svc = _make_service(mock_db)
        outbox_events = []
        with (
            patch.object(
                svc._repo,
                "get_earning_by_transaction",
                new=AsyncMock(return_value=None),
            ),
            patch.object(
                svc._repo, "list_peer_contact_names", new=AsyncMock(return_value=[])
            ),
            patch.object(svc._repo, "list_sources", new=AsyncMock(return_value=[])),
            patch.object(
                svc._repo,
                "find_recurring_source_match",
                new=AsyncMock(return_value=None),
            ),
            patch.object(
                svc._repo,
                "add_outbox_event",
                new=AsyncMock(side_effect=lambda et, p: outbox_events.append((et, p))),
            ),
        ):
            await svc.handle_transaction_created(
                {
                    "transaction_id": str(TRANSACTION_ID),
                    "user_id": str(USER_ID),
                    "amount": Decimal("1500.00"),
                    "currency": "INR",
                    "date": "2026-04-25",
                    "type": "credit",
                    "raw_description": "IMPS received",
                }
            )
        assert outbox_events[0][0] == "earnings.EarningClassificationNeeded"

    async def test_transaction_created_existing_earning_is_idempotent(self, mock_db):
        svc = _make_service(mock_db)
        with (
            patch.object(
                svc._repo,
                "get_earning_by_transaction",
                new=AsyncMock(
                    return_value=_make_earning(transaction_id=TRANSACTION_ID)
                ),
            ),
            patch.object(
                svc._repo,
                "find_recurring_source_match",
                new=AsyncMock(return_value=None),
            ),
            patch.object(svc._repo, "create_earning", new=AsyncMock()) as mock_create,
        ):
            await svc.handle_transaction_created(
                {
                    "transaction_id": str(TRANSACTION_ID),
                    "user_id": str(USER_ID),
                    "amount": Decimal("1500.00"),
                    "currency": "INR",
                    "date": "2026-04-25",
                    "type": "credit",
                    "raw_description": "NEFT SALARY",
                }
            )
        mock_create.assert_not_called()
