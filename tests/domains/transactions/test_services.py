"""
Service-layer tests for the transactions domain.

All external dependencies (DB session, repository, cross-domain reads) are mocked.
No real database or network connections are made.
"""
from __future__ import annotations

import hashlib
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tests.conftest import USER_ID, make_test_settings


# ── Helpers ────────────────────────────────────────────────────────────────────

def _make_service(mock_db):
    from elixir.domains.transactions.services import TransactionsService

    return TransactionsService(db=mock_db, settings=make_test_settings())


ACCOUNT_ID = uuid.uuid4()
TRANSACTION_ID = uuid.uuid4()
CATEGORY_ID = uuid.uuid4()
CATEGORY_ID_2 = uuid.uuid4()


def _fingerprint(description: str | None, txn_date: date, amount: Decimal) -> str:
    normalized = ((description or "").strip().lower() + txn_date.isoformat() + str(amount))
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _make_item(
    item_id=None,
    transaction_id=None,
    category_id=None,
    amount=Decimal("500.00"),
    currency="INR",
    label=None,
    is_primary=True,
):
    item = MagicMock()
    item.id = item_id or uuid.uuid4()
    item.transaction_id = transaction_id or TRANSACTION_ID
    item.category_id = category_id or CATEGORY_ID
    item.amount = amount
    item.currency = currency
    item.label = label
    item.is_primary = is_primary
    item.updated_at = None
    return item


def _make_transaction(
    transaction_id=None,
    user_id=None,
    account_id=None,
    account_kind="bank",
    amount=Decimal("500.00"),
    currency="INR",
    txn_date=date(2026, 4, 25),
    txn_type="debit",
    source="manual",
    raw_description="Swiggy",
    notes="Friday dinner",
    fingerprint=None,
    items=None,
):
    txn = MagicMock()
    txn.id = transaction_id or TRANSACTION_ID
    txn.user_id = user_id or USER_ID
    txn.account_id = account_id or ACCOUNT_ID
    txn.account_kind = account_kind
    txn.amount = amount
    txn.currency = currency
    txn.date = txn_date
    txn.type = txn_type
    txn.source = source
    txn.raw_description = raw_description
    txn.notes = notes
    txn.fingerprint = fingerprint
    txn.created_at = datetime.now(timezone.utc)
    txn.updated_at = None
    txn.items = items or [_make_item(transaction_id=txn.id, amount=amount)]
    return txn


def _make_list_row(
    transaction_id=None,
    account_id=None,
    amount=Decimal("500.00"),
    txn_date=date(2026, 4, 25),
    txn_type="debit",
    source="manual",
    raw_description="Swiggy order",
    notes="Friday dinner",
    account_name="SBI Savings",
    account_kind="bank",
    primary_category_id=None,
    primary_category_name="Food & Dining",
):
    row = MagicMock()
    row.id = transaction_id or uuid.uuid4()
    row.account_id = account_id or ACCOUNT_ID
    row.amount = amount
    row.currency = "INR"
    row.date = txn_date
    row.type = txn_type
    row.source = source
    row.raw_description = raw_description
    row.notes = notes
    row.account_name = account_name
    row.account_kind = account_kind
    row.primary_category_id = primary_category_id or CATEGORY_ID
    row.primary_category_name = primary_category_name
    row.created_at = datetime.now(timezone.utc)
    return row


# ── add_transaction tests ──────────────────────────────────────────────────────

class TestAddTransaction:
    async def test_add_transaction_creates_manual_transaction_items_and_outbox_events(self, mock_db):
        """Happy path: manual entry creates the transaction, its items, and both outbox events."""
        from elixir.domains.transactions.schemas import TransactionCreate

        svc = _make_service(mock_db)
        transaction = _make_transaction(notes="Friday dinner")
        outbox_events: list[tuple[str, dict]] = []

        data = TransactionCreate(
            account_id=ACCOUNT_ID,
            account_kind="bank",
            amount=Decimal("500.00"),
            currency="INR",
            date=date(2026, 4, 25),
            type="debit",
            raw_description="Swiggy",
            notes="Friday dinner",
            items=[
                {
                    "category_id": CATEGORY_ID,
                    "amount": Decimal("500.00"),
                    "label": None,
                }
            ],
        )

        with patch.object(
            svc._repo,
            "category_ids_exist",
            new=AsyncMock(return_value=True),
            create=True,
        ), patch.object(
            svc._repo,
            "create_transaction",
            new=AsyncMock(return_value=transaction),
            create=True,
        ), patch.object(
            svc._repo,
            "create_transaction_items",
            new=AsyncMock(return_value=transaction.items),
            create=True,
        ), patch.object(
            svc._repo,
            "add_outbox_event",
            new=AsyncMock(side_effect=lambda et, p: outbox_events.append((et, p))),
            create=True,
        ):
            result = await svc.add_transaction(USER_ID, data)

        assert result.id == transaction.id
        assert result.source == "manual"
        assert result.notes == "Friday dinner"
        mock_db.commit.assert_called_once()

        assert len(outbox_events) == 2
        created_event, categorized_event = outbox_events

        assert created_event[0] == "transactions.TransactionCreated"
        assert created_event[1]["user_id"] == str(USER_ID)
        assert created_event[1]["account_id"] == str(ACCOUNT_ID)
        assert created_event[1]["amount"] == "500.00"
        assert created_event[1]["type"] == "debit"
        assert created_event[1]["source"] == "manual"

        assert categorized_event[0] == "transactions.TransactionCategorized"
        assert categorized_event[1]["transaction_id"] == str(transaction.id)
        assert categorized_event[1]["items"] == [
            {
                "category_id": str(CATEGORY_ID),
                "amount": "500.00",
                "currency": "INR",
                "label": None,
            }
        ]

    async def test_add_transaction_item_amount_mismatch_raises_422(self, mock_db):
        """When item amounts do not sum to the transaction amount, ItemAmountMismatchError is raised."""
        from elixir.domains.transactions.schemas import TransactionCreate
        from elixir.shared.exceptions import ItemAmountMismatchError

        svc = _make_service(mock_db)
        data = TransactionCreate(
            account_id=ACCOUNT_ID,
            account_kind="bank",
            amount=Decimal("500.00"),
            currency="INR",
            date=date(2026, 4, 25),
            type="debit",
            raw_description="Amazon",
            items=[
                {
                    "category_id": CATEGORY_ID,
                    "amount": Decimal("300.00"),
                    "label": "Headphones",
                }
            ],
        )

        with pytest.raises(ItemAmountMismatchError):
            await svc.add_transaction(USER_ID, data)

        mock_db.commit.assert_not_called()

    async def test_add_transaction_zero_amount_raises_validation_error(self, mock_db):
        """Zero-amount transactions are rejected by the request schema."""
        from pydantic import ValidationError
        from elixir.domains.transactions.schemas import TransactionCreate

        with pytest.raises(ValidationError):
            TransactionCreate(
                account_id=ACCOUNT_ID,
                account_kind="bank",
                amount=Decimal("0.00"),
                currency="INR",
                date=date(2026, 4, 25),
                type="debit",
                raw_description="Cash entry",
                items=[
                    {
                        "category_id": CATEGORY_ID,
                        "amount": Decimal("0.00"),
                        "label": None,
                    }
                ],
            )


# ── edit_transaction tests ────────────────────────────────────────────────────

class TestEditTransaction:
    async def test_edit_transaction_updates_notes_items_and_writes_transaction_updated_event(self, mock_db):
        """Happy path: editing notes and category breakdown replaces items and emits TransactionUpdated."""
        from elixir.domains.transactions.schemas import TransactionUpdate

        svc = _make_service(mock_db)
        old_items = [
            _make_item(category_id=CATEGORY_ID, amount=Decimal("500.00"), label=None),
        ]
        new_items = [
            _make_item(category_id=CATEGORY_ID_2, amount=Decimal("300.00"), label="Meal"),
            _make_item(
                category_id=CATEGORY_ID,
                amount=Decimal("200.00"),
                label="Delivery fee",
                is_primary=False,
            ),
        ]
        transaction = _make_transaction(items=old_items, notes="Old note")
        outbox_events: list[tuple[str, dict]] = []

        data = TransactionUpdate(
            notes="Updated note",
            items=[
                {
                    "category_id": CATEGORY_ID_2,
                    "amount": Decimal("300.00"),
                    "label": "Meal",
                },
                {
                    "category_id": CATEGORY_ID,
                    "amount": Decimal("200.00"),
                    "label": "Delivery fee",
                },
            ],
        )

        with patch.object(
            svc._repo,
            "get_transaction",
            new=AsyncMock(return_value=transaction),
            create=True,
        ), patch.object(
            svc._repo,
            "get_transaction_items",
            new=AsyncMock(return_value=old_items),
            create=True,
        ), patch.object(
            svc._repo,
            "category_ids_exist",
            new=AsyncMock(return_value=True),
            create=True,
        ), patch.object(
            svc._repo,
            "update_transaction",
            new=AsyncMock(return_value=None),
            create=True,
        ), patch.object(
            svc._repo,
            "replace_transaction_items",
            new=AsyncMock(return_value=new_items),
            create=True,
        ), patch.object(
            svc._repo,
            "add_outbox_event",
            new=AsyncMock(side_effect=lambda et, p: outbox_events.append((et, p))),
            create=True,
        ):
            result = await svc.edit_transaction(USER_ID, transaction.id, data)

        assert result.id == transaction.id
        mock_db.commit.assert_called_once()

        assert len(outbox_events) == 1
        event_type, payload = outbox_events[0]
        assert event_type == "transactions.TransactionUpdated"
        assert payload["transaction_id"] == str(transaction.id)
        assert payload["user_id"] == str(USER_ID)
        assert set(payload["changed_fields"]) == {"notes", "items"}
        assert payload["old_items"] == [
            {
                "category_id": str(CATEGORY_ID),
                "amount": "500.00",
                "label": None,
                "currency": "INR",
            }
        ]
        assert payload["new_items"] == [
            {
                "category_id": str(CATEGORY_ID_2),
                "amount": "300.00",
                "label": "Meal",
                "currency": "INR",
            },
            {
                "category_id": str(CATEGORY_ID),
                "amount": "200.00",
                "label": "Delivery fee",
                "currency": "INR",
            },
        ]

    async def test_edit_transaction_not_found_raises_404(self, mock_db):
        """When the transaction is not found for the user, TransactionNotFoundError is raised."""
        from elixir.domains.transactions.schemas import TransactionUpdate
        from elixir.shared.exceptions import TransactionNotFoundError

        svc = _make_service(mock_db)

        with patch.object(
            svc._repo,
            "get_transaction",
            new=AsyncMock(return_value=None),
            create=True,
        ):
            with pytest.raises(TransactionNotFoundError):
                await svc.edit_transaction(USER_ID, uuid.uuid4(), TransactionUpdate(notes="Updated"))

        mock_db.commit.assert_not_called()

    async def test_edit_transaction_item_amount_mismatch_raises_422(self, mock_db):
        """Editing items with a split that does not match the parent amount raises ItemAmountMismatchError."""
        from elixir.domains.transactions.schemas import TransactionUpdate
        from elixir.shared.exceptions import ItemAmountMismatchError

        svc = _make_service(mock_db)
        transaction = _make_transaction(amount=Decimal("500.00"))
        data = TransactionUpdate(
            items=[
                {
                    "category_id": CATEGORY_ID,
                    "amount": Decimal("499.00"),
                    "label": None,
                }
            ]
        )

        with patch.object(
            svc._repo,
            "get_transaction",
            new=AsyncMock(return_value=transaction),
            create=True,
        ):
            with pytest.raises(ItemAmountMismatchError):
                await svc.edit_transaction(USER_ID, transaction.id, data)

        mock_db.commit.assert_not_called()


# ── list/get transaction tests ────────────────────────────────────────────────

class TestListTransactions:
    async def test_list_transactions_returns_paginated_summaries_for_filters(self, mock_db):
        """Listing returns paginated transaction summaries with account and primary category display fields."""
        from elixir.domains.transactions.schemas import TransactionFilters
        from elixir.shared.pagination import PagedResponse

        svc = _make_service(mock_db)
        row = _make_list_row()
        repo_page = PagedResponse(items=[row], total=1, page=1, page_size=50)
        filters = TransactionFilters(
            account_id=ACCOUNT_ID,
            category_id=CATEGORY_ID,
            type="debit",
            source="manual",
            search_text="swiggy",
        )

        with patch.object(
            svc._repo,
            "list_transactions",
            new=AsyncMock(return_value=repo_page),
            create=True,
        ) as mock_list:
            result = await svc.list_transactions(USER_ID, filters=filters, page=1, page_size=50)

        assert result.total == 1
        assert result.page == 1
        assert result.page_size == 50
        assert len(result.items) == 1
        assert result.items[0].account_name == "SBI Savings"
        assert result.items[0].primary_category_name == "Food & Dining"
        mock_list.assert_called_once_with(USER_ID, filters, 1, 50)


class TestGetTransaction:
    async def test_get_transaction_returns_transaction_with_all_items(self, mock_db):
        """Happy path: get_transaction returns the full transaction detail with its items."""
        svc = _make_service(mock_db)
        items = [
            _make_item(category_id=CATEGORY_ID, amount=Decimal("300.00"), label="Meal"),
            _make_item(
                category_id=CATEGORY_ID_2,
                amount=Decimal("200.00"),
                label="Dessert",
                is_primary=False,
            ),
        ]
        transaction = _make_transaction(items=items)

        with patch.object(
            svc._repo,
            "get_transaction",
            new=AsyncMock(return_value=transaction),
            create=True,
        ):
            result = await svc.get_transaction(USER_ID, transaction.id)

        assert result.id == transaction.id
        assert result.raw_description == "Swiggy"
        assert len(result.items) == 2
        assert result.items[0].amount == Decimal("300.00")
        assert result.items[1].label == "Dessert"

    async def test_get_transaction_not_found_raises_404(self, mock_db):
        """When the transaction is not found for the user, TransactionNotFoundError is raised."""
        from elixir.shared.exceptions import TransactionNotFoundError

        svc = _make_service(mock_db)

        with patch.object(
            svc._repo,
            "get_transaction",
            new=AsyncMock(return_value=None),
            create=True,
        ):
            with pytest.raises(TransactionNotFoundError):
                await svc.get_transaction(USER_ID, uuid.uuid4())


# ── import / event-driven creation tests ──────────────────────────────────────

class TestCreateTransactionsFromClassifiedRows:
    async def test_create_transactions_from_classified_rows_inserts_new_rows_and_publishes_events(self, mock_db):
        """Happy path: classified rows create transactions/items and publish both downstream events."""
        svc = _make_service(mock_db)
        created_transactions = [
            _make_transaction(
                transaction_id=uuid.uuid4(),
                account_id=ACCOUNT_ID,
                txn_date=date(2026, 4, 20),
                amount=Decimal("500.00"),
                source="statement_import",
                raw_description="Swiggy",
                notes=None,
                items=[_make_item(category_id=CATEGORY_ID, amount=Decimal("500.00"))],
            ),
            _make_transaction(
                transaction_id=uuid.uuid4(),
                account_id=ACCOUNT_ID,
                txn_date=date(2026, 4, 21),
                amount=Decimal("1200.00"),
                source="statement_import",
                raw_description="Salary credit",
                txn_type="credit",
                notes=None,
                items=[_make_item(category_id=CATEGORY_ID_2, amount=Decimal("1200.00"))],
            ),
        ]
        outbox_events: list[tuple[str, dict]] = []
        rows = [
            {
                "date": date(2026, 4, 20),
                "description": "  Swiggy  ",
                "amount": Decimal("500.00"),
                "currency": "INR",
                "type": "debit",
                "category_id": CATEGORY_ID,
            },
            {
                "date": date(2026, 4, 21),
                "description": "Salary Credit",
                "amount": Decimal("1200.00"),
                "currency": "INR",
                "type": "credit",
                "category_id": CATEGORY_ID_2,
            },
        ]

        with patch.object(
            svc._repo,
            "fingerprint_exists",
            new=AsyncMock(side_effect=[False, False]),
            create=True,
        ) as mock_exists, patch.object(
            svc._repo,
            "create_transaction",
            new=AsyncMock(side_effect=created_transactions),
            create=True,
        ), patch.object(
            svc._repo,
            "create_transaction_items",
            new=AsyncMock(side_effect=[t.items for t in created_transactions]),
            create=True,
        ), patch.object(
            svc._repo,
            "add_outbox_event",
            new=AsyncMock(side_effect=lambda et, p: outbox_events.append((et, p))),
            create=True,
        ), patch.object(
            svc,
            "_detect_transfers",
            new=AsyncMock(return_value=None),
            create=True,
        ) as mock_detect:
            await svc.create_transactions_from_classified_rows(
                user_id=USER_ID,
                account_id=ACCOUNT_ID,
                account_kind="bank",
                rows=rows,
                source="statement_import",
            )

        assert mock_exists.await_count == 2
        assert mock_exists.await_args_list[0].args == (
            USER_ID,
            _fingerprint("  Swiggy  ", date(2026, 4, 20), Decimal("500.00")),
        )
        assert mock_exists.await_args_list[1].args == (
            USER_ID,
            _fingerprint("Salary Credit", date(2026, 4, 21), Decimal("1200.00")),
        )
        assert len(outbox_events) == 4
        assert [event_type for event_type, _ in outbox_events] == [
            "transactions.TransactionCreated",
            "transactions.TransactionCategorized",
            "transactions.TransactionCreated",
            "transactions.TransactionCategorized",
        ]
        mock_detect.assert_awaited_once_with(
            USER_ID,
            [created_transactions[0].id, created_transactions[1].id],
        )
        mock_db.commit.assert_called_once()

    async def test_create_transactions_from_classified_rows_skips_duplicate_fingerprints(self, mock_db):
        """Idempotency: rows with an existing fingerprint are skipped silently and do not emit events."""
        svc = _make_service(mock_db)
        new_transaction = _make_transaction(
            transaction_id=uuid.uuid4(),
            account_id=ACCOUNT_ID,
            txn_date=date(2026, 4, 24),
            amount=Decimal("700.00"),
            source="bulk_import",
            raw_description="New merchant",
            notes=None,
            items=[_make_item(category_id=CATEGORY_ID_2, amount=Decimal("700.00"))],
        )
        rows = [
            {
                "date": date(2026, 4, 23),
                "description": "Duplicate merchant",
                "amount": Decimal("500.00"),
                "currency": "INR",
                "type": "debit",
                "category_id": CATEGORY_ID,
            },
            {
                "date": date(2026, 4, 24),
                "description": "New merchant",
                "amount": Decimal("700.00"),
                "currency": "INR",
                "type": "debit",
                "category_id": CATEGORY_ID_2,
            },
        ]

        with patch.object(
            svc._repo,
            "fingerprint_exists",
            new=AsyncMock(side_effect=[True, False]),
            create=True,
        ), patch.object(
            svc._repo,
            "create_transaction",
            new=AsyncMock(return_value=new_transaction),
            create=True,
        ) as mock_create_transaction, patch.object(
            svc._repo,
            "create_transaction_items",
            new=AsyncMock(return_value=new_transaction.items),
            create=True,
        ) as mock_create_items, patch.object(
            svc._repo,
            "add_outbox_event",
            new=AsyncMock(return_value=None),
            create=True,
        ) as mock_outbox, patch.object(
            svc,
            "_detect_transfers",
            new=AsyncMock(return_value=None),
            create=True,
        ) as mock_detect:
            await svc.create_transactions_from_classified_rows(
                user_id=USER_ID,
                account_id=ACCOUNT_ID,
                account_kind="bank",
                rows=rows,
                source="bulk_import",
            )

        mock_create_transaction.assert_awaited_once()
        create_kwargs = mock_create_transaction.await_args.kwargs
        assert create_kwargs["user_id"] == USER_ID
        assert create_kwargs["account_id"] == ACCOUNT_ID
        assert create_kwargs["account_kind"] == "bank"
        assert create_kwargs["source"] == "bulk_import"
        assert create_kwargs["fingerprint"] == _fingerprint(
            "New merchant",
            date(2026, 4, 24),
            Decimal("700.00"),
        )
        mock_create_items.assert_awaited_once()
        assert mock_outbox.await_count == 2
        mock_detect.assert_awaited_once_with(USER_ID, [new_transaction.id])
        mock_db.commit.assert_called_once()
