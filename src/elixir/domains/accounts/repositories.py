import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from elixir.domains.accounts.models import AccountsOutbox, BankAccount, CreditCard


class AccountsRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    # ── Bank Accounts ─────────────────────────────────────────────────────────

    async def create_bank_account(
        self,
        user_id: uuid.UUID,
        nickname: str,
        bank_name: str,
        account_type: str,
        last4: str | None = None,
        currency: str = "INR",
    ) -> BankAccount:
        acct = BankAccount(
            user_id=user_id,
            nickname=nickname,
            bank_name=bank_name,
            account_type=account_type,
            last4=last4,
            currency=currency,
        )
        self._db.add(acct)
        await self._db.flush()
        return acct

    async def get_bank_account(
        self, user_id: uuid.UUID, account_id: uuid.UUID
    ) -> BankAccount | None:
        result = await self._db.execute(
            select(BankAccount).where(
                BankAccount.id == account_id,
                BankAccount.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    async def update_bank_account(self, account: BankAccount, **fields: Any) -> None:
        for key, value in fields.items():
            if value is not None:
                setattr(account, key, value)
        account.updated_at = datetime.now(timezone.utc)

    async def deactivate_bank_account(self, account: BankAccount) -> None:
        account.is_active = False
        account.updated_at = datetime.now(timezone.utc)

    # ── Credit Cards ──────────────────────────────────────────────────────────

    async def create_credit_card(
        self,
        user_id: uuid.UUID,
        nickname: str,
        bank_name: str,
        card_network: str | None = None,
        last4: str | None = None,
        credit_limit: Any | None = None,
        billing_cycle_day: int | None = None,
        currency: str = "INR",
    ) -> CreditCard:
        card = CreditCard(
            user_id=user_id,
            nickname=nickname,
            bank_name=bank_name,
            card_network=card_network,
            last4=last4,
            credit_limit=credit_limit,
            billing_cycle_day=billing_cycle_day,
            currency=currency,
        )
        self._db.add(card)
        await self._db.flush()
        return card

    async def get_credit_card(
        self, user_id: uuid.UUID, card_id: uuid.UUID
    ) -> CreditCard | None:
        result = await self._db.execute(
            select(CreditCard).where(
                CreditCard.id == card_id,
                CreditCard.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    async def update_credit_card(self, card: CreditCard, **fields: Any) -> None:
        for key, value in fields.items():
            if value is not None:
                setattr(card, key, value)
        card.updated_at = datetime.now(timezone.utc)

    async def deactivate_credit_card(self, card: CreditCard) -> None:
        card.is_active = False
        card.updated_at = datetime.now(timezone.utc)

    # ── Accounts summary view (cross-domain read) ─────────────────────────────

    async def list_accounts(self, user_id: uuid.UUID) -> list[dict[str, Any]]:
        """
        Query the user_accounts_summary view filtered by user_id.
        Returns a list of plain dicts — safe for cross-domain consumption.
        """
        result = await self._db.execute(
            text(
                "SELECT id, user_id, nickname, bank_name, account_kind, subtype, "
                "last4, currency, is_active "
                "FROM user_accounts_summary "
                "WHERE user_id = :user_id AND is_active = true"
            ),
            {"user_id": str(user_id)},
        )
        rows = result.mappings().all()
        return [dict(row) for row in rows]

    # ── Outbox ────────────────────────────────────────────────────────────────

    async def add_outbox_event(self, event_type: str, payload: dict[str, Any]) -> None:
        row = AccountsOutbox(event_type=event_type, payload=payload)
        self._db.add(row)
