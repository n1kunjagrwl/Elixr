import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from elixir.domains.accounts.events import AccountLinked, AccountRemoved
from elixir.domains.accounts.repositories import AccountsRepository
from elixir.domains.accounts.schemas import (
    AccountSummaryResponse,
    BankAccountCreate,
    BankAccountResponse,
    BankAccountUpdate,
    CreditCardCreate,
    CreditCardResponse,
    CreditCardUpdate,
)
from elixir.shared.config import Settings
from elixir.shared.exceptions import AccountNotFoundError


class AccountsService:
    def __init__(self, db: AsyncSession, settings: Settings) -> None:
        self._db = db
        self._repo = AccountsRepository(db)
        self._settings = settings

    # ── Bank Accounts ─────────────────────────────────────────────────────────

    async def add_bank_account(
        self, user_id: uuid.UUID, data: BankAccountCreate
    ) -> BankAccountResponse:
        acct = await self._repo.create_bank_account(
            user_id=user_id,
            nickname=data.nickname,
            bank_name=data.bank_name,
            account_type=data.account_type,
            last4=data.last4,
            currency=data.currency,
        )
        event = AccountLinked(
            account_id=str(acct.id),
            user_id=str(user_id),
            account_kind="bank",
            nickname=acct.nickname,
        )
        await self._repo.add_outbox_event(event.event_type, event.to_payload())
        await self._db.commit()
        return BankAccountResponse.model_validate(acct)

    async def edit_bank_account(
        self,
        user_id: uuid.UUID,
        account_id: uuid.UUID,
        data: BankAccountUpdate,
    ) -> BankAccountResponse:
        acct = await self._repo.get_bank_account(user_id, account_id)
        if acct is None:
            raise AccountNotFoundError(f"Bank account {account_id} not found.")
        update_fields = data.model_dump(exclude_unset=True, exclude_none=True)
        if update_fields:
            await self._repo.update_bank_account(acct, **update_fields)
        await self._db.commit()
        return BankAccountResponse.model_validate(acct)

    async def deactivate_bank_account(
        self, user_id: uuid.UUID, account_id: uuid.UUID
    ) -> None:
        acct = await self._repo.get_bank_account(user_id, account_id)
        if acct is None:
            raise AccountNotFoundError(f"Bank account {account_id} not found.")
        await self._repo.deactivate_bank_account(acct)
        event = AccountRemoved(
            account_id=str(account_id),
            user_id=str(user_id),
            account_kind="bank",
        )
        await self._repo.add_outbox_event(event.event_type, event.to_payload())
        await self._db.commit()

    # ── Credit Cards ──────────────────────────────────────────────────────────

    async def add_credit_card(
        self, user_id: uuid.UUID, data: CreditCardCreate
    ) -> CreditCardResponse:
        card = await self._repo.create_credit_card(
            user_id=user_id,
            nickname=data.nickname,
            bank_name=data.bank_name,
            card_network=data.card_network,
            last4=data.last4,
            credit_limit=data.credit_limit,
            billing_cycle_day=data.billing_cycle_day,
            currency=data.currency,
        )
        event = AccountLinked(
            account_id=str(card.id),
            user_id=str(user_id),
            account_kind="credit_card",
            nickname=card.nickname,
        )
        await self._repo.add_outbox_event(event.event_type, event.to_payload())
        await self._db.commit()
        return CreditCardResponse.model_validate(card)

    async def edit_credit_card(
        self,
        user_id: uuid.UUID,
        card_id: uuid.UUID,
        data: CreditCardUpdate,
    ) -> CreditCardResponse:
        card = await self._repo.get_credit_card(user_id, card_id)
        if card is None:
            raise AccountNotFoundError(f"Credit card {card_id} not found.")
        update_fields = data.model_dump(exclude_unset=True, exclude_none=True)
        if update_fields:
            await self._repo.update_credit_card(card, **update_fields)
        await self._db.commit()
        return CreditCardResponse.model_validate(card)

    async def deactivate_credit_card(
        self, user_id: uuid.UUID, card_id: uuid.UUID
    ) -> None:
        card = await self._repo.get_credit_card(user_id, card_id)
        if card is None:
            raise AccountNotFoundError(f"Credit card {card_id} not found.")
        await self._repo.deactivate_credit_card(card)
        event = AccountRemoved(
            account_id=str(card_id),
            user_id=str(user_id),
            account_kind="credit_card",
        )
        await self._repo.add_outbox_event(event.event_type, event.to_payload())
        await self._db.commit()

    # ── Summary (cross-domain read view) ──────────────────────────────────────

    async def list_accounts(self, user_id: uuid.UUID) -> list[AccountSummaryResponse]:
        rows = await self._repo.list_accounts(user_id)
        return [AccountSummaryResponse(**row) for row in rows]
