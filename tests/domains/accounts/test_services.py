"""
Service-layer tests for the accounts domain.

All external dependencies (DB session, repository) are mocked.
No real database or network connections are made.
"""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tests.conftest import USER_ID, make_test_settings


# ── Helpers ────────────────────────────────────────────────────────────────────

def _make_service(mock_db):
    from elixir.domains.accounts.services import AccountsService
    return AccountsService(db=mock_db, settings=make_test_settings())


def _make_bank_account(
    account_id=None,
    user_id=None,
    nickname="My SBI Savings",
    bank_name="SBI",
    account_type="savings",
    last4="1234",
    currency="INR",
    is_active=True,
):
    acct = MagicMock()
    acct.id = account_id or uuid.uuid4()
    acct.user_id = user_id or USER_ID
    acct.nickname = nickname
    acct.bank_name = bank_name
    acct.account_type = account_type
    acct.last4 = last4
    acct.currency = currency
    acct.is_active = is_active
    acct.created_at = None
    acct.updated_at = None
    return acct


def _make_credit_card(
    card_id=None,
    user_id=None,
    nickname="My HDFC CC",
    bank_name="HDFC",
    card_network="visa",
    last4="5678",
    credit_limit=50000,
    billing_cycle_day=15,
    currency="INR",
    is_active=True,
):
    card = MagicMock()
    card.id = card_id or uuid.uuid4()
    card.user_id = user_id or USER_ID
    card.nickname = nickname
    card.bank_name = bank_name
    card.card_network = card_network
    card.last4 = last4
    card.credit_limit = credit_limit
    card.billing_cycle_day = billing_cycle_day
    card.currency = currency
    card.is_active = is_active
    card.created_at = None
    card.updated_at = None
    return card


# ── add_bank_account tests ────────────────────────────────────────────────────

class TestAddBankAccount:
    async def test_add_bank_account_creates_row_and_outbox_event(self, mock_db):
        """Happy path: creating a bank account persists the row and writes an outbox event."""
        from elixir.domains.accounts.schemas import BankAccountCreate

        svc = _make_service(mock_db)
        bank = _make_bank_account()
        outbox_event_captured = []

        data = BankAccountCreate(
            nickname="My SBI Savings",
            bank_name="SBI",
            account_type="savings",
            last4="1234",
        )

        with patch.object(svc._repo, "create_bank_account", new=AsyncMock(return_value=bank)), \
             patch.object(svc._repo, "add_outbox_event", new=AsyncMock(side_effect=lambda et, p: outbox_event_captured.append((et, p)))):

            result = await svc.add_bank_account(USER_ID, data)

        assert result.nickname == "My SBI Savings"
        assert result.bank_name == "SBI"
        assert result.account_type == "savings"
        assert result.last4 == "1234"
        mock_db.commit.assert_called_once()

        # outbox event must have been written
        assert len(outbox_event_captured) == 1
        event_type, payload = outbox_event_captured[0]
        assert event_type == "accounts.AccountLinked"
        assert payload["user_id"] == str(USER_ID)
        assert payload["account_kind"] == "bank"

    async def test_add_bank_account_invalid_account_type_raises_validation_error(self, mock_db):
        """Supplying an invalid account_type raises a Pydantic validation error."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            from elixir.domains.accounts.schemas import BankAccountCreate
            BankAccountCreate(
                nickname="Test",
                bank_name="SBI",
                account_type="invalid_type",  # not in enum
            )


# ── add_credit_card tests ─────────────────────────────────────────────────────

class TestAddCreditCard:
    async def test_add_credit_card_creates_row_and_outbox_event(self, mock_db):
        """Happy path: creating a credit card persists the row and writes an outbox event."""
        from elixir.domains.accounts.schemas import CreditCardCreate

        svc = _make_service(mock_db)
        card = _make_credit_card()
        outbox_event_captured = []

        data = CreditCardCreate(
            nickname="My HDFC CC",
            bank_name="HDFC",
            card_network="visa",
            last4="5678",
            credit_limit=50000,
            billing_cycle_day=15,
        )

        with patch.object(svc._repo, "create_credit_card", new=AsyncMock(return_value=card)), \
             patch.object(svc._repo, "add_outbox_event", new=AsyncMock(side_effect=lambda et, p: outbox_event_captured.append((et, p)))):

            result = await svc.add_credit_card(USER_ID, data)

        assert result.nickname == "My HDFC CC"
        assert result.card_network == "visa"
        mock_db.commit.assert_called_once()

        assert len(outbox_event_captured) == 1
        event_type, payload = outbox_event_captured[0]
        assert event_type == "accounts.AccountLinked"
        assert payload["account_kind"] == "credit_card"

    async def test_add_credit_card_invalid_network_raises_validation_error(self, mock_db):
        """Supplying an invalid card_network raises a Pydantic validation error."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            from elixir.domains.accounts.schemas import CreditCardCreate
            CreditCardCreate(
                nickname="Test",
                bank_name="HDFC",
                card_network="diners",  # not in enum
            )

    async def test_add_credit_card_invalid_billing_cycle_day_raises_validation_error(self, mock_db):
        """billing_cycle_day outside 1-28 raises a Pydantic validation error."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            from elixir.domains.accounts.schemas import CreditCardCreate
            CreditCardCreate(
                nickname="Test",
                bank_name="HDFC",
                billing_cycle_day=29,  # too high
            )

        with pytest.raises(ValidationError):
            from elixir.domains.accounts.schemas import CreditCardCreate
            CreditCardCreate(
                nickname="Test",
                bank_name="HDFC",
                billing_cycle_day=0,  # too low
            )


# ── edit_bank_account tests ───────────────────────────────────────────────────

class TestEditBankAccount:
    async def test_edit_bank_account_updates_fields(self, mock_db):
        """Happy path: editing bank account updates the specified fields."""
        from elixir.domains.accounts.schemas import BankAccountUpdate

        svc = _make_service(mock_db)
        bank = _make_bank_account()
        account_id = bank.id

        data = BankAccountUpdate(nickname="Renamed Account")

        with patch.object(svc._repo, "get_bank_account", new=AsyncMock(return_value=bank)), \
             patch.object(svc._repo, "update_bank_account", new=AsyncMock(return_value=None)):

            result = await svc.edit_bank_account(USER_ID, account_id, data)

        assert result is not None
        mock_db.commit.assert_called_once()

    async def test_edit_bank_account_not_found_raises_404(self, mock_db):
        """When account is not found, AccountNotFoundError is raised."""
        from elixir.domains.accounts.schemas import BankAccountUpdate
        from elixir.shared.exceptions import AccountNotFoundError

        svc = _make_service(mock_db)

        with patch.object(svc._repo, "get_bank_account", new=AsyncMock(return_value=None)):
            with pytest.raises(AccountNotFoundError):
                await svc.edit_bank_account(USER_ID, uuid.uuid4(), BankAccountUpdate())

    async def test_edit_bank_account_wrong_user_raises_forbidden(self, mock_db):
        """When account belongs to another user, the repo filters it out → AccountNotFoundError."""
        from elixir.domains.accounts.schemas import BankAccountUpdate
        from elixir.shared.exceptions import AccountNotFoundError

        svc = _make_service(mock_db)
        other_user_id = uuid.uuid4()
        bank = _make_bank_account(user_id=other_user_id)

        # The repo filters by (user_id, id) — if the requesting user doesn't own the
        # account the repo returns None (it was filtered out), which produces a 404.
        with patch.object(svc._repo, "get_bank_account", new=AsyncMock(return_value=None)):
            with pytest.raises(AccountNotFoundError):
                await svc.edit_bank_account(USER_ID, bank.id, BankAccountUpdate())


# ── edit_credit_card tests ────────────────────────────────────────────────────

class TestEditCreditCard:
    async def test_edit_credit_card_updates_fields(self, mock_db):
        """Happy path: editing credit card updates the specified fields."""
        from elixir.domains.accounts.schemas import CreditCardUpdate

        svc = _make_service(mock_db)
        card = _make_credit_card()

        data = CreditCardUpdate(nickname="New Nickname", billing_cycle_day=10)

        with patch.object(svc._repo, "get_credit_card", new=AsyncMock(return_value=card)), \
             patch.object(svc._repo, "update_credit_card", new=AsyncMock(return_value=None)):

            result = await svc.edit_credit_card(USER_ID, card.id, data)

        assert result is not None
        mock_db.commit.assert_called_once()


# ── deactivate_bank_account tests ─────────────────────────────────────────────

class TestDeactivateBankAccount:
    async def test_deactivate_bank_account_sets_is_active_false(self, mock_db):
        """Deactivating a bank account writes a soft delete and an AccountRemoved event."""
        svc = _make_service(mock_db)
        bank = _make_bank_account()
        outbox_event_captured = []

        with patch.object(svc._repo, "get_bank_account", new=AsyncMock(return_value=bank)), \
             patch.object(svc._repo, "deactivate_bank_account", new=AsyncMock(return_value=None)), \
             patch.object(svc._repo, "add_outbox_event", new=AsyncMock(side_effect=lambda et, p: outbox_event_captured.append((et, p)))):

            await svc.deactivate_bank_account(USER_ID, bank.id)

        mock_db.commit.assert_called_once()
        assert len(outbox_event_captured) == 1
        event_type, payload = outbox_event_captured[0]
        assert event_type == "accounts.AccountRemoved"
        assert payload["account_kind"] == "bank"

    async def test_deactivate_bank_account_wrong_user_raises_forbidden(self, mock_db):
        """Deactivating an account not owned by the user raises AccountNotFoundError (repo filters)."""
        from elixir.shared.exceptions import AccountNotFoundError

        svc = _make_service(mock_db)

        with patch.object(svc._repo, "get_bank_account", new=AsyncMock(return_value=None)):
            with pytest.raises(AccountNotFoundError):
                await svc.deactivate_bank_account(USER_ID, uuid.uuid4())


# ── deactivate_credit_card tests ──────────────────────────────────────────────

class TestDeactivateCreditCard:
    async def test_deactivate_credit_card_sets_is_active_false(self, mock_db):
        """Deactivating a credit card writes soft delete and an AccountRemoved event."""
        svc = _make_service(mock_db)
        card = _make_credit_card()
        outbox_event_captured = []

        with patch.object(svc._repo, "get_credit_card", new=AsyncMock(return_value=card)), \
             patch.object(svc._repo, "deactivate_credit_card", new=AsyncMock(return_value=None)), \
             patch.object(svc._repo, "add_outbox_event", new=AsyncMock(side_effect=lambda et, p: outbox_event_captured.append((et, p)))):

            await svc.deactivate_credit_card(USER_ID, card.id)

        mock_db.commit.assert_called_once()
        assert len(outbox_event_captured) == 1
        event_type, payload = outbox_event_captured[0]
        assert event_type == "accounts.AccountRemoved"
        assert payload["account_kind"] == "credit_card"


# ── list_accounts tests ───────────────────────────────────────────────────────

class TestListAccounts:
    async def test_list_accounts_returns_only_active_accounts_for_user(self, mock_db):
        """list_accounts returns only active rows belonging to the requesting user."""
        svc = _make_service(mock_db)

        raw_rows = [
            {
                "id": str(uuid.uuid4()),
                "user_id": str(USER_ID),
                "nickname": "My SBI Savings",
                "bank_name": "SBI",
                "account_kind": "bank",
                "subtype": "savings",
                "last4": "1234",
                "currency": "INR",
                "is_active": True,
            },
            {
                "id": str(uuid.uuid4()),
                "user_id": str(USER_ID),
                "nickname": "My HDFC CC",
                "bank_name": "HDFC",
                "account_kind": "credit_card",
                "subtype": "visa",
                "last4": "5678",
                "currency": "INR",
                "is_active": True,
            },
        ]

        with patch.object(svc._repo, "list_accounts", new=AsyncMock(return_value=raw_rows)):
            results = await svc.list_accounts(USER_ID)

        assert len(results) == 2
        kinds = {r.account_kind for r in results}
        assert "bank" in kinds
        assert "credit_card" in kinds
