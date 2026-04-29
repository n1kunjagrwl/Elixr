import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from elixir.domains.peers.models import PeerBalance, PeerContact, PeerSettlement


class PeersRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    # ── Contacts ──────────────────────────────────────────────────────────────

    async def create_contact(
        self,
        user_id: uuid.UUID,
        name: str,
        phone: str | None = None,
        notes: str | None = None,
    ) -> PeerContact:
        contact = PeerContact(
            user_id=user_id,
            name=name,
            phone=phone,
            notes=notes,
        )
        self._db.add(contact)
        await self._db.flush()
        return contact

    async def get_contact(
        self, user_id: uuid.UUID, contact_id: uuid.UUID
    ) -> PeerContact | None:
        result = await self._db.execute(
            select(PeerContact).where(
                PeerContact.id == contact_id,
                PeerContact.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_contacts(self, user_id: uuid.UUID) -> list[PeerContact]:
        result = await self._db.execute(
            select(PeerContact)
            .where(PeerContact.user_id == user_id)
            .order_by(PeerContact.name)
        )
        return list(result.scalars().all())

    async def update_contact(self, contact: PeerContact, **fields: Any) -> None:
        for key, value in fields.items():
            setattr(contact, key, value)
        contact.updated_at = datetime.now(timezone.utc)

    async def delete_contact(self, contact: PeerContact) -> None:
        await self._db.delete(contact)

    async def has_open_balances(
        self, user_id: uuid.UUID, contact_id: uuid.UUID
    ) -> bool:
        """Return True if the contact has any open or partial balance for this user."""
        result = await self._db.execute(
            select(PeerBalance.id)
            .where(
                PeerBalance.peer_id == contact_id,
                PeerBalance.user_id == user_id,
                PeerBalance.status.in_(["open", "partial"]),
            )
            .limit(1)
        )
        return result.scalar_one_or_none() is not None

    # ── Balances ──────────────────────────────────────────────────────────────

    async def create_balance(
        self,
        user_id: uuid.UUID,
        peer_id: uuid.UUID,
        description: str,
        original_amount: Any,
        currency: str = "INR",
        direction: str = "owed_to_me",
        linked_transaction_id: uuid.UUID | None = None,
        notes: str | None = None,
    ) -> PeerBalance:
        balance = PeerBalance(
            user_id=user_id,
            peer_id=peer_id,
            description=description,
            original_amount=original_amount,
            settled_amount=0,
            currency=currency,
            direction=direction,
            status="open",
            linked_transaction_id=linked_transaction_id,
            notes=notes,
        )
        self._db.add(balance)
        await self._db.flush()
        return balance

    async def get_balance(
        self, user_id: uuid.UUID, balance_id: uuid.UUID
    ) -> PeerBalance | None:
        result = await self._db.execute(
            select(PeerBalance).where(
                PeerBalance.id == balance_id,
                PeerBalance.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_balances(
        self, user_id: uuid.UUID, status: str | None = None
    ) -> list[PeerBalance]:
        query = select(PeerBalance).where(PeerBalance.user_id == user_id)
        if status is not None:
            query = query.where(PeerBalance.status == status)
        query = query.order_by(PeerBalance.created_at.desc())
        result = await self._db.execute(query)
        return list(result.scalars().all())

    async def update_balance(self, balance: PeerBalance, **fields: Any) -> None:
        for key, value in fields.items():
            setattr(balance, key, value)
        balance.updated_at = datetime.now(timezone.utc)

    async def update_balance_settled_amount(
        self, balance: PeerBalance, new_settled_amount: Any, new_status: str
    ) -> None:
        balance.settled_amount = new_settled_amount
        balance.status = new_status
        balance.updated_at = datetime.now(timezone.utc)

    async def refresh_balance(
        self, user_id: uuid.UUID, balance_id: uuid.UUID
    ) -> PeerBalance | None:
        """Re-fetch the balance from DB so the generated column is up to date."""
        await self._db.flush()
        result = await self._db.execute(
            select(PeerBalance).where(
                PeerBalance.id == balance_id,
                PeerBalance.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    # ── Settlements ───────────────────────────────────────────────────────────

    async def create_settlement(
        self,
        balance_id: uuid.UUID,
        amount: Any,
        settled_at: datetime,
        currency: str = "INR",
        method: str | None = None,
        linked_transaction_id: uuid.UUID | None = None,
        notes: str | None = None,
    ) -> PeerSettlement:
        settlement = PeerSettlement(
            balance_id=balance_id,
            amount=amount,
            currency=currency,
            settled_at=settled_at,
            method=method,
            linked_transaction_id=linked_transaction_id,
            notes=notes,
        )
        self._db.add(settlement)
        await self._db.flush()
        return settlement

    async def list_settlements(self, balance_id: uuid.UUID) -> list[PeerSettlement]:
        result = await self._db.execute(
            select(PeerSettlement)
            .where(PeerSettlement.balance_id == balance_id)
            .order_by(PeerSettlement.settled_at.asc())
        )
        return list(result.scalars().all())
