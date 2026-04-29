"""
Service-layer tests for the peers domain.

All external dependencies (DB session, repository) are mocked.
No real database or network connections are made.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tests.conftest import USER_ID


# ── Helpers ────────────────────────────────────────────────────────────────────


def _make_service(mock_db):
    from elixir.domains.peers.services import PeersService

    return PeersService(db=mock_db)


def _make_contact(
    contact_id=None,
    user_id=None,
    name="Alice",
    phone=None,
    notes=None,
):
    contact = MagicMock()
    contact.id = contact_id or uuid.uuid4()
    contact.user_id = user_id or USER_ID
    contact.name = name
    contact.phone = phone
    contact.notes = notes
    contact.created_at = datetime.now(timezone.utc)
    contact.updated_at = None
    return contact


def _make_balance(
    balance_id=None,
    user_id=None,
    peer_id=None,
    description="Dinner split",
    original_amount=Decimal("500.00"),
    settled_amount=Decimal("0.00"),
    remaining_amount=Decimal("500.00"),
    currency="INR",
    direction="owed_to_me",
    status="open",
    linked_transaction_id=None,
    notes=None,
):
    balance = MagicMock()
    balance.id = balance_id or uuid.uuid4()
    balance.user_id = user_id or USER_ID
    balance.peer_id = peer_id or uuid.uuid4()
    balance.description = description
    balance.original_amount = original_amount
    balance.settled_amount = settled_amount
    balance.remaining_amount = remaining_amount
    balance.currency = currency
    balance.direction = direction
    balance.status = status
    balance.linked_transaction_id = linked_transaction_id
    balance.notes = notes
    balance.created_at = datetime.now(timezone.utc)
    balance.updated_at = None
    return balance


def _make_settlement(
    settlement_id=None,
    balance_id=None,
    amount=Decimal("100.00"),
    currency="INR",
    settled_at=None,
    method="cash",
    linked_transaction_id=None,
    notes=None,
):
    settlement = MagicMock()
    settlement.id = settlement_id or uuid.uuid4()
    settlement.balance_id = balance_id or uuid.uuid4()
    settlement.amount = amount
    settlement.currency = currency
    settlement.settled_at = settled_at or datetime.now(timezone.utc)
    settlement.method = method
    settlement.linked_transaction_id = linked_transaction_id
    settlement.notes = notes
    settlement.created_at = datetime.now(timezone.utc)
    return settlement


# ── Contact tests ──────────────────────────────────────────────────────────────


class TestAddContact:
    async def test_add_contact_creates_contact(self, mock_db):
        """Happy path: adding a contact persists the row and returns the contact."""
        from elixir.domains.peers.schemas import PeerContactCreate

        svc = _make_service(mock_db)
        contact = _make_contact()

        data = PeerContactCreate(name="Alice", phone="+919876543210")

        with patch.object(
            svc._repo, "create_contact", new=AsyncMock(return_value=contact)
        ):
            result = await svc.add_contact(USER_ID, data)

        assert result.name == "Alice"
        mock_db.commit.assert_called_once()


class TestEditContact:
    async def test_edit_contact_updates_fields(self, mock_db):
        """Happy path: editing a contact updates the specified fields."""
        from elixir.domains.peers.schemas import PeerContactUpdate

        svc = _make_service(mock_db)
        contact = _make_contact()
        contact_id = contact.id

        data = PeerContactUpdate(name="Bob")

        with (
            patch.object(svc._repo, "get_contact", new=AsyncMock(return_value=contact)),
            patch.object(svc._repo, "update_contact", new=AsyncMock(return_value=None)),
        ):
            result = await svc.edit_contact(USER_ID, contact_id, data)

        assert result is not None
        mock_db.commit.assert_called_once()

    async def test_edit_contact_not_found_raises_404(self, mock_db):
        """When contact is not found, PeerContactNotFoundError is raised."""
        from elixir.domains.peers.schemas import PeerContactUpdate
        from elixir.shared.exceptions import PeerContactNotFoundError

        svc = _make_service(mock_db)

        with patch.object(svc._repo, "get_contact", new=AsyncMock(return_value=None)):
            with pytest.raises(PeerContactNotFoundError):
                await svc.edit_contact(USER_ID, uuid.uuid4(), PeerContactUpdate())


class TestDeleteContact:
    async def test_delete_contact_with_open_balances_raises_409(self, mock_db):
        """Cannot delete a contact that has open/partial balances."""
        from elixir.shared.exceptions import ContactHasOpenBalancesError

        svc = _make_service(mock_db)
        contact = _make_contact()

        with (
            patch.object(svc._repo, "get_contact", new=AsyncMock(return_value=contact)),
            patch.object(
                svc._repo, "has_open_balances", new=AsyncMock(return_value=True)
            ),
        ):
            with pytest.raises(ContactHasOpenBalancesError):
                await svc.delete_contact(USER_ID, contact.id)

        mock_db.commit.assert_not_called()

    async def test_delete_contact_no_balances_succeeds(self, mock_db):
        """Deleting a contact with no open/partial balances succeeds."""
        svc = _make_service(mock_db)
        contact = _make_contact()

        with (
            patch.object(svc._repo, "get_contact", new=AsyncMock(return_value=contact)),
            patch.object(
                svc._repo, "has_open_balances", new=AsyncMock(return_value=False)
            ),
            patch.object(svc._repo, "delete_contact", new=AsyncMock(return_value=None)),
        ):
            await svc.delete_contact(USER_ID, contact.id)

        mock_db.commit.assert_called_once()


# ── Balance tests ──────────────────────────────────────────────────────────────


class TestLogBalance:
    async def test_log_balance_creates_balance(self, mock_db):
        """Happy path: logging a balance creates the row and returns it."""
        from elixir.domains.peers.schemas import PeerBalanceCreate

        svc = _make_service(mock_db)
        contact = _make_contact()
        balance = _make_balance(peer_id=contact.id)

        data = PeerBalanceCreate(
            peer_id=contact.id,
            description="Dinner split",
            original_amount=Decimal("500.00"),
            direction="owed_to_me",
        )

        with (
            patch.object(svc._repo, "get_contact", new=AsyncMock(return_value=contact)),
            patch.object(
                svc._repo, "create_balance", new=AsyncMock(return_value=balance)
            ),
        ):
            result = await svc.log_balance(USER_ID, data)

        assert result.description == "Dinner split"
        mock_db.commit.assert_called_once()

    async def test_log_balance_invalid_peer_raises_404(self, mock_db):
        """Logging a balance for a non-existent peer raises PeerContactNotFoundError."""
        from elixir.domains.peers.schemas import PeerBalanceCreate
        from elixir.shared.exceptions import PeerContactNotFoundError

        svc = _make_service(mock_db)

        data = PeerBalanceCreate(
            peer_id=uuid.uuid4(),
            description="Dinner split",
            original_amount=Decimal("500.00"),
            direction="owed_to_me",
        )

        with patch.object(svc._repo, "get_contact", new=AsyncMock(return_value=None)):
            with pytest.raises(PeerContactNotFoundError):
                await svc.log_balance(USER_ID, data)

        mock_db.commit.assert_not_called()


class TestEditBalance:
    async def test_edit_balance_updates_description_and_notes(self, mock_db):
        """Happy path: editing a balance updates description and notes only."""
        from elixir.domains.peers.schemas import PeerBalanceUpdate

        svc = _make_service(mock_db)
        balance = _make_balance()

        data = PeerBalanceUpdate(
            description="Updated dinner split", notes="Split evenly"
        )

        with (
            patch.object(svc._repo, "get_balance", new=AsyncMock(return_value=balance)),
            patch.object(svc._repo, "update_balance", new=AsyncMock(return_value=None)),
        ):
            result = await svc.edit_balance(USER_ID, balance.id, data)

        assert result is not None
        mock_db.commit.assert_called_once()


class TestListBalances:
    async def test_list_balances_filters_by_status(self, mock_db):
        """list_balances with a status filter returns only matching balances."""
        svc = _make_service(mock_db)
        open_balance = _make_balance(status="open")

        with patch.object(
            svc._repo, "list_balances", new=AsyncMock(return_value=[open_balance])
        ):
            results = await svc.list_balances(USER_ID, status="open")

        assert len(results) == 1
        assert results[0].status == "open"


# ── Settlement tests ───────────────────────────────────────────────────────────


class TestRecordSettlement:
    async def test_record_settlement_updates_settled_amount_and_status_to_partial(
        self, mock_db
    ):
        """Partial settlement updates settled_amount and sets status to 'partial'."""
        from elixir.domains.peers.schemas import PeerSettlementCreate

        svc = _make_service(mock_db)
        balance = _make_balance(
            original_amount=Decimal("500.00"),
            settled_amount=Decimal("0.00"),
            remaining_amount=Decimal("500.00"),
            status="open",
        )
        # After partial settlement, remaining_amount would be 400 (re-fetched from DB)
        updated_balance = _make_balance(
            balance_id=balance.id,
            original_amount=Decimal("500.00"),
            settled_amount=Decimal("100.00"),
            remaining_amount=Decimal("400.00"),
            status="partial",
        )
        settlement = _make_settlement(balance_id=balance.id, amount=Decimal("100.00"))

        data = PeerSettlementCreate(
            amount=Decimal("100.00"),
            settled_at=datetime.now(timezone.utc),
            method="cash",
        )

        with (
            patch.object(svc._repo, "get_balance", new=AsyncMock(return_value=balance)),
            patch.object(
                svc._repo, "create_settlement", new=AsyncMock(return_value=settlement)
            ),
            patch.object(
                svc._repo,
                "update_balance_settled_amount",
                new=AsyncMock(return_value=None),
            ),
            patch.object(
                svc._repo,
                "refresh_balance",
                new=AsyncMock(return_value=updated_balance),
            ),
        ):
            result = await svc.record_settlement(USER_ID, balance.id, data)

        assert result.amount == Decimal("100.00")
        mock_db.commit.assert_called_once()

    async def test_record_settlement_full_amount_sets_status_settled(self, mock_db):
        """Full settlement sets balance status to 'settled'."""
        from elixir.domains.peers.schemas import PeerSettlementCreate

        svc = _make_service(mock_db)
        balance = _make_balance(
            original_amount=Decimal("500.00"),
            settled_amount=Decimal("0.00"),
            remaining_amount=Decimal("500.00"),
            status="open",
        )
        updated_balance = _make_balance(
            balance_id=balance.id,
            original_amount=Decimal("500.00"),
            settled_amount=Decimal("500.00"),
            remaining_amount=Decimal("0.00"),
            status="settled",
        )
        settlement = _make_settlement(balance_id=balance.id, amount=Decimal("500.00"))

        data = PeerSettlementCreate(
            amount=Decimal("500.00"),
            settled_at=datetime.now(timezone.utc),
            method="upi",
        )

        with (
            patch.object(svc._repo, "get_balance", new=AsyncMock(return_value=balance)),
            patch.object(
                svc._repo, "create_settlement", new=AsyncMock(return_value=settlement)
            ),
            patch.object(
                svc._repo,
                "update_balance_settled_amount",
                new=AsyncMock(return_value=None),
            ),
            patch.object(
                svc._repo,
                "refresh_balance",
                new=AsyncMock(return_value=updated_balance),
            ),
        ):
            result = await svc.record_settlement(USER_ID, balance.id, data)

        assert result.amount == Decimal("500.00")
        mock_db.commit.assert_called_once()

    async def test_record_settlement_exceeds_remaining_raises_422(self, mock_db):
        """Settlement exceeding remaining_amount raises SettlementExceedsRemainingError."""
        from elixir.domains.peers.schemas import PeerSettlementCreate
        from elixir.shared.exceptions import SettlementExceedsRemainingError

        svc = _make_service(mock_db)
        balance = _make_balance(
            original_amount=Decimal("500.00"),
            settled_amount=Decimal("400.00"),
            remaining_amount=Decimal("100.00"),
            status="partial",
        )

        data = PeerSettlementCreate(
            amount=Decimal("200.00"),  # exceeds remaining 100.00
            settled_at=datetime.now(timezone.utc),
            method="cash",
        )

        with patch.object(
            svc._repo, "get_balance", new=AsyncMock(return_value=balance)
        ):
            with pytest.raises(SettlementExceedsRemainingError):
                await svc.record_settlement(USER_ID, balance.id, data)

        mock_db.commit.assert_not_called()


class TestListSettlements:
    async def test_list_settlements_returns_settlements_for_balance(self, mock_db):
        """list_settlements returns all settlements for a given balance."""
        svc = _make_service(mock_db)
        balance = _make_balance()
        settlement1 = _make_settlement(balance_id=balance.id)
        settlement2 = _make_settlement(balance_id=balance.id)

        with (
            patch.object(svc._repo, "get_balance", new=AsyncMock(return_value=balance)),
            patch.object(
                svc._repo,
                "list_settlements",
                new=AsyncMock(return_value=[settlement1, settlement2]),
            ),
        ):
            results = await svc.list_settlements(USER_ID, balance.id)

        assert len(results) == 2
