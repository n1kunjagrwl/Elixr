"""
NotificationsService — converts domain events into user-facing in-app notifications.

No business logic beyond message formatting and idempotency checks.
"""

from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from elixir.domains.notifications.repositories import NotificationsRepository
from elixir.domains.notifications.schemas import NotificationResponse
from elixir.shared.exceptions import NotificationNotFoundError


class NotificationsService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._repo = NotificationsRepository(db)

    # ── Public API ─────────────────────────────────────────────────────────────

    async def list_notifications(
        self,
        user_id: uuid.UUID,
        unread_only: bool = False,
        page: int = 1,
        page_size: int = 20,
    ) -> list[NotificationResponse]:
        rows = await self._repo.list_notifications(
            user_id, unread_only=unread_only, page=page, page_size=page_size
        )
        return [NotificationResponse.model_validate(r) for r in rows]

    async def mark_read(self, user_id: uuid.UUID, notification_id: uuid.UUID) -> None:
        notification = await self._repo.get_notification(user_id, notification_id)
        if notification is None:
            raise NotificationNotFoundError(
                f"Notification {notification_id} not found."
            )
        await self._repo.mark_read(notification)
        await self._db.commit()

    async def mark_all_read(self, user_id: uuid.UUID) -> dict:
        count = await self._repo.mark_all_read(user_id)
        await self._db.commit()
        return {"marked": count}

    # ── Idempotent insert ──────────────────────────────────────────────────────

    async def _create_if_not_exists(
        self,
        user_id: uuid.UUID,
        type_: str,
        title: str,
        body: str,
        route: str,
        primary_entity_id: uuid.UUID | None = None,
        secondary_entity_id: uuid.UUID | None = None,
        period_start: date | None = None,
    ) -> None:
        already = await self._repo.notification_exists(
            user_id=user_id,
            type_=type_,
            primary_entity_id=primary_entity_id,
            secondary_entity_id=secondary_entity_id,
            period_start=period_start,
        )
        if already:
            return
        await self._repo.create_notification(
            user_id=user_id,
            type_=type_,
            title=title,
            body=body,
            route=route,
            primary_entity_id=primary_entity_id,
            secondary_entity_id=secondary_entity_id,
            period_start=period_start,
        )
        await self._db.commit()

    # ── Event-driven builders ──────────────────────────────────────────────────

    async def _on_account_linked(
        self,
        user_id: uuid.UUID,
        account_id: uuid.UUID,
        nickname: str,
    ) -> None:
        await self._create_if_not_exists(
            user_id=user_id,
            type_="accounts.AccountLinked",
            title="Account added",
            body=f"Upload a statement or log a transaction to start tracking {nickname}.",
            route="/statements/upload",
            primary_entity_id=account_id,
        )

    async def _on_extraction_completed(
        self,
        user_id: uuid.UUID,
        job_id: uuid.UUID,
        n: int,
        account_name: str,
    ) -> None:
        await self._create_if_not_exists(
            user_id=user_id,
            type_="statements.ExtractionCompleted",
            title="Statement processed",
            body=f"{n} transactions from your {account_name} statement are ready to review.",
            route=f"/statements/{job_id}/review",
            primary_entity_id=job_id,
        )

    async def _on_extraction_partially_completed(
        self,
        user_id: uuid.UUID,
        job_id: uuid.UUID,
        n: int,
        discarded_from: int,
        discarded_to: int,
    ) -> None:
        await self._create_if_not_exists(
            user_id=user_id,
            type_="statements.ExtractionPartiallyCompleted",
            title="Statement partially imported",
            body=f"{n} transactions imported. Rows from {discarded_from} to {discarded_to} were discarded.",
            route="/statements/upload",
            primary_entity_id=job_id,
        )

    async def _on_earning_classification_needed(
        self,
        user_id: uuid.UUID,
        transaction_id: uuid.UUID,
        currency: str,
        amount: str,
    ) -> None:
        await self._create_if_not_exists(
            user_id=user_id,
            type_="earnings.EarningClassificationNeeded",
            title="New credit to classify",
            body=f"{currency} {amount} received — is this income or a repayment?",
            route="/earnings/classify",
            primary_entity_id=transaction_id,
        )

    async def _on_sip_detected(
        self,
        user_id: uuid.UUID,
        transaction_id: uuid.UUID,
        sip_registration_id: uuid.UUID,
        currency: str,
        amount: str,
        instrument_name: str,
    ) -> None:
        await self._create_if_not_exists(
            user_id=user_id,
            type_="investments.SIPDetected",
            title="SIP payment detected",
            body=f"{currency} {amount} to {instrument_name} — confirm to link this SIP.",
            route="/investments/sip/confirm",
            primary_entity_id=transaction_id,
            secondary_entity_id=sip_registration_id,
        )

    async def _on_budget_limit_warning(
        self,
        user_id: uuid.UUID,
        goal_id: uuid.UUID,
        percent: int,
        period_start: date,
    ) -> None:
        await self._create_if_not_exists(
            user_id=user_id,
            type_="budgets.BudgetLimitWarning",
            title="Approaching budget limit",
            body=f"You've used {percent}% of your budget for this period.",
            route="/budgets",
            primary_entity_id=goal_id,
            period_start=period_start,
        )

    async def _on_budget_limit_breached(
        self,
        user_id: uuid.UUID,
        goal_id: uuid.UUID,
        currency: str,
        spent: str,
        limit: str,
        period_start: date,
    ) -> None:
        await self._create_if_not_exists(
            user_id=user_id,
            type_="budgets.BudgetLimitBreached",
            title="Budget limit exceeded",
            body=f"You've exceeded your budget limit for this period. Spent {currency} {spent} against a limit of {currency} {limit}.",
            route="/budgets",
            primary_entity_id=goal_id,
            period_start=period_start,
        )

    async def _on_import_completed(
        self,
        user_id: uuid.UUID,
        job_id: uuid.UUID,
        imported_rows: int,
        skipped_rows: int,
    ) -> None:
        await self._create_if_not_exists(
            user_id=user_id,
            type_="import_.ImportCompleted",
            title="Import complete",
            body=f"{imported_rows} transactions imported, {skipped_rows} skipped.",
            route="/transactions",
            primary_entity_id=job_id,
        )
