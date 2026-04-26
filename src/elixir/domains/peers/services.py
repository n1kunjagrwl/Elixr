import uuid
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from elixir.domains.peers.repositories import PeersRepository
from elixir.domains.peers.schemas import (
    PeerBalanceCreate,
    PeerBalanceResponse,
    PeerBalanceUpdate,
    PeerContactCreate,
    PeerContactResponse,
    PeerContactUpdate,
    PeerSettlementCreate,
    PeerSettlementResponse,
)
from elixir.shared.exceptions import (
    ContactHasOpenBalancesError,
    PeerBalanceNotFoundError,
    PeerContactNotFoundError,
    SettlementExceedsRemainingError,
)


class PeersService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._repo = PeersRepository(db)

    # ── Contacts ──────────────────────────────────────────────────────────────

    async def list_contacts(self, user_id: uuid.UUID) -> list[PeerContactResponse]:
        contacts = await self._repo.list_contacts(user_id)
        return [PeerContactResponse.model_validate(c) for c in contacts]

    async def add_contact(
        self, user_id: uuid.UUID, data: PeerContactCreate
    ) -> PeerContactResponse:
        contact = await self._repo.create_contact(
            user_id=user_id,
            name=data.name,
            phone=data.phone,
            notes=data.notes,
        )
        await self._db.commit()
        return PeerContactResponse.model_validate(contact)

    async def edit_contact(
        self,
        user_id: uuid.UUID,
        contact_id: uuid.UUID,
        data: PeerContactUpdate,
    ) -> PeerContactResponse:
        contact = await self._repo.get_contact(user_id, contact_id)
        if contact is None:
            raise PeerContactNotFoundError(f"Peer contact {contact_id} not found.")
        update_fields = data.model_dump(exclude_unset=True)
        if update_fields:
            await self._repo.update_contact(contact, **update_fields)
        await self._db.commit()
        return PeerContactResponse.model_validate(contact)

    async def delete_contact(
        self, user_id: uuid.UUID, contact_id: uuid.UUID
    ) -> None:
        contact = await self._repo.get_contact(user_id, contact_id)
        if contact is None:
            raise PeerContactNotFoundError(f"Peer contact {contact_id} not found.")
        has_open = await self._repo.has_open_balances(user_id, contact_id)
        if has_open:
            raise ContactHasOpenBalancesError(
                f"Contact {contact_id} has open or partial balances."
            )
        await self._repo.delete_contact(contact)
        await self._db.commit()

    # ── Balances ──────────────────────────────────────────────────────────────

    async def list_balances(
        self, user_id: uuid.UUID, status: str | None = None
    ) -> list[PeerBalanceResponse]:
        balances = await self._repo.list_balances(user_id, status=status)
        return [PeerBalanceResponse.model_validate(b) for b in balances]

    async def log_balance(
        self, user_id: uuid.UUID, data: PeerBalanceCreate
    ) -> PeerBalanceResponse:
        # Validate that the peer contact belongs to this user
        contact = await self._repo.get_contact(user_id, data.peer_id)
        if contact is None:
            raise PeerContactNotFoundError(f"Peer contact {data.peer_id} not found.")

        balance = await self._repo.create_balance(
            user_id=user_id,
            peer_id=data.peer_id,
            description=data.description,
            original_amount=data.original_amount,
            currency=data.currency,
            direction=data.direction,
            linked_transaction_id=data.linked_transaction_id,
            notes=data.notes,
        )
        await self._db.commit()
        return PeerBalanceResponse.model_validate(balance)

    async def edit_balance(
        self,
        user_id: uuid.UUID,
        balance_id: uuid.UUID,
        data: PeerBalanceUpdate,
    ) -> PeerBalanceResponse:
        balance = await self._repo.get_balance(user_id, balance_id)
        if balance is None:
            raise PeerBalanceNotFoundError(f"Peer balance {balance_id} not found.")
        update_fields = data.model_dump(exclude_unset=True)
        if update_fields:
            await self._repo.update_balance(balance, **update_fields)
        await self._db.commit()
        return PeerBalanceResponse.model_validate(balance)

    # ── Settlements ───────────────────────────────────────────────────────────

    async def list_settlements(
        self, user_id: uuid.UUID, balance_id: uuid.UUID
    ) -> list[PeerSettlementResponse]:
        balance = await self._repo.get_balance(user_id, balance_id)
        if balance is None:
            raise PeerBalanceNotFoundError(f"Peer balance {balance_id} not found.")
        settlements = await self._repo.list_settlements(balance_id)
        return [PeerSettlementResponse.model_validate(s) for s in settlements]

    async def record_settlement(
        self,
        user_id: uuid.UUID,
        balance_id: uuid.UUID,
        data: PeerSettlementCreate,
    ) -> PeerSettlementResponse:
        balance = await self._repo.get_balance(user_id, balance_id)
        if balance is None:
            raise PeerBalanceNotFoundError(f"Peer balance {balance_id} not found.")

        if data.amount > balance.remaining_amount:
            raise SettlementExceedsRemainingError(
                f"Settlement amount {data.amount} exceeds remaining {balance.remaining_amount}."
            )

        settlement = await self._repo.create_settlement(
            balance_id=balance_id,
            amount=data.amount,
            currency=data.currency,
            settled_at=data.settled_at,
            method=data.method,
            linked_transaction_id=data.linked_transaction_id,
            notes=data.notes,
        )

        new_settled = Decimal(str(balance.settled_amount)) + Decimal(str(data.amount))
        original = Decimal(str(balance.original_amount))

        if new_settled >= original:
            new_status = "settled"
        elif new_settled > 0:
            new_status = "partial"
        else:
            new_status = "open"

        await self._repo.update_balance_settled_amount(balance, new_settled, new_status)

        # remaining_amount is a DB generated column — always re-fetch after update
        await self._repo.refresh_balance(user_id, balance_id)

        await self._db.commit()
        return PeerSettlementResponse.model_validate(settlement)
