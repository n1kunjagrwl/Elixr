"""
Notifications domain event handlers.

Each handler subscribes to a domain event, builds notification content,
and calls the service to create a deduplicated notification.
"""
from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from elixir.shared.events import EventPayload


async def handle_account_linked(payload: EventPayload, session: AsyncSession) -> None:
    """Create notification when a bank account or credit card is linked."""
    from elixir.domains.notifications.services import NotificationsService

    service = NotificationsService(db=session)
    user_id = uuid.UUID(payload["user_id"])
    account_id = uuid.UUID(payload["account_id"])
    nickname: str = payload.get("nickname", "your account")

    await service._on_account_linked(
        user_id=user_id,
        account_id=account_id,
        nickname=nickname,
    )


async def handle_extraction_completed(payload: EventPayload, session: AsyncSession) -> None:
    """Create notification when statement extraction finishes successfully."""
    from elixir.domains.notifications.services import NotificationsService

    service = NotificationsService(db=session)
    user_id = uuid.UUID(payload["user_id"])
    job_id = uuid.UUID(payload["job_id"])
    n: int = int(payload.get("transaction_count", 0))
    account_name: str = payload.get("account_name", "your")

    await service._on_extraction_completed(
        user_id=user_id,
        job_id=job_id,
        n=n,
        account_name=account_name,
    )


async def handle_extraction_partially_completed(
    payload: EventPayload, session: AsyncSession
) -> None:
    """Create notification when statement extraction completes with discarded rows."""
    from elixir.domains.notifications.services import NotificationsService

    service = NotificationsService(db=session)
    user_id = uuid.UUID(payload["user_id"])
    job_id = uuid.UUID(payload["job_id"])
    n: int = int(payload.get("transaction_count", 0))
    discarded_from: int = int(payload.get("discarded_from", 0))
    discarded_to: int = int(payload.get("discarded_to", 0))

    await service._on_extraction_partially_completed(
        user_id=user_id,
        job_id=job_id,
        n=n,
        discarded_from=discarded_from,
        discarded_to=discarded_to,
    )


async def handle_earning_classification_needed(
    payload: EventPayload, session: AsyncSession
) -> None:
    """Create notification when a credit transaction needs income/repayment classification."""
    from elixir.domains.notifications.services import NotificationsService

    service = NotificationsService(db=session)
    user_id = uuid.UUID(payload["user_id"])
    transaction_id = uuid.UUID(payload["transaction_id"])
    currency: str = payload.get("currency", "INR")
    amount: str = str(payload.get("amount", "0"))

    await service._on_earning_classification_needed(
        user_id=user_id,
        transaction_id=transaction_id,
        currency=currency,
        amount=amount,
    )


async def handle_sip_detected(payload: EventPayload, session: AsyncSession) -> None:
    """Create notification when a recurring SIP payment is detected."""
    from elixir.domains.notifications.services import NotificationsService

    service = NotificationsService(db=session)
    user_id = uuid.UUID(payload["user_id"])
    transaction_id = uuid.UUID(payload["transaction_id"])
    sip_registration_id = uuid.UUID(payload["sip_registration_id"])
    currency: str = payload.get("currency", "INR")
    amount: str = str(payload.get("amount", "0"))
    instrument_name: str = payload.get("instrument_name", "your fund")

    await service._on_sip_detected(
        user_id=user_id,
        transaction_id=transaction_id,
        sip_registration_id=sip_registration_id,
        currency=currency,
        amount=amount,
        instrument_name=instrument_name,
    )


async def handle_budget_limit_warning(payload: EventPayload, session: AsyncSession) -> None:
    """Create notification when spending reaches the 80% budget threshold."""
    from elixir.domains.notifications.services import NotificationsService

    service = NotificationsService(db=session)
    user_id = uuid.UUID(payload["user_id"])
    goal_id = uuid.UUID(payload["goal_id"])
    percent: int = int(payload.get("percent_used", 80))
    period_start: date = date.fromisoformat(payload["period_start"])

    await service._on_budget_limit_warning(
        user_id=user_id,
        goal_id=goal_id,
        percent=percent,
        period_start=period_start,
    )


async def handle_budget_limit_breached(payload: EventPayload, session: AsyncSession) -> None:
    """Create notification when spending exceeds the 100% budget threshold."""
    from elixir.domains.notifications.services import NotificationsService

    service = NotificationsService(db=session)
    user_id = uuid.UUID(payload["user_id"])
    goal_id = uuid.UUID(payload["goal_id"])
    currency: str = payload.get("currency", "INR")
    spent: str = str(payload.get("current_spend", "0"))
    limit: str = str(payload.get("limit_amount", "0"))
    period_start: date = date.fromisoformat(payload["period_start"])

    await service._on_budget_limit_breached(
        user_id=user_id,
        goal_id=goal_id,
        currency=currency,
        spent=spent,
        limit=limit,
        period_start=period_start,
    )


async def handle_import_completed(payload: EventPayload, session: AsyncSession) -> None:
    """Create notification when a CSV/file import job finishes."""
    from elixir.domains.notifications.services import NotificationsService

    service = NotificationsService(db=session)
    user_id = uuid.UUID(payload["user_id"])
    job_id = uuid.UUID(payload["job_id"])
    imported_rows: int = int(payload.get("imported_rows", 0))
    skipped_rows: int = int(payload.get("skipped_rows", 0))

    await service._on_import_completed(
        user_id=user_id,
        job_id=job_id,
        imported_rows=imported_rows,
        skipped_rows=skipped_rows,
    )
