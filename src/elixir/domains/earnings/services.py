from __future__ import annotations

import uuid
from datetime import date
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from elixir.domains.earnings.events import (
    EarningClassificationNeeded,
    EarningRecorded,
)
from elixir.domains.earnings.repositories import EarningsRepository
from elixir.domains.earnings.schemas import (
    ClassifyTransactionRequest,
    EarningCreate,
    EarningFilters,
    EarningResponse,
    EarningSourceCreate,
    EarningSourceResponse,
    EarningSourceUpdate,
    EarningUpdate,
)
from elixir.shared.exceptions import (
    EarningNotFoundError,
    EarningSourceNotFoundError,
    TransactionNotFoundError,
    TransactionAlreadyClassifiedError,
)

_INCOME_KEYWORDS = ("SALARY", "PAYROLL", "EMPLOYER", "CREDIT SAL")


class EarningsService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._repo = EarningsRepository(db)

    async def list_sources(self, user_id: uuid.UUID) -> list[EarningSourceResponse]:
        sources = await self._repo.list_sources(user_id)
        return [EarningSourceResponse.model_validate(source) for source in sources]

    async def add_source(
        self, user_id: uuid.UUID, data: EarningSourceCreate
    ) -> EarningSourceResponse:
        source = await self._repo.create_source(user_id, data.name, data.type)
        await self._db.commit()
        return EarningSourceResponse.model_validate(source)

    async def edit_source(
        self,
        user_id: uuid.UUID,
        source_id: uuid.UUID,
        data: EarningSourceUpdate,
    ) -> EarningSourceResponse:
        source = await self._repo.get_source(user_id, source_id)
        if source is None:
            raise EarningSourceNotFoundError(f"Earning source {source_id} not found.")
        fields = data.model_dump(exclude_unset=True)
        if fields:
            await self._repo.update_source(source, **fields)
        await self._db.commit()
        return EarningSourceResponse.model_validate(source)

    async def deactivate_source(self, user_id: uuid.UUID, source_id: uuid.UUID) -> None:
        source = await self._repo.get_source(user_id, source_id)
        if source is None:
            raise EarningSourceNotFoundError(f"Earning source {source_id} not found.")
        await self._repo.update_source(source, is_active=False)
        await self._db.commit()

    async def add_manual_earning(
        self, user_id: uuid.UUID, data: EarningCreate
    ) -> EarningResponse:
        source = await self._resolve_source(user_id, data.source_id)
        source_type = source.type if source is not None else data.source_type
        source_label = data.source_label if source is None else source.name
        self._validate_source_fields(
            source_type=source_type,
            source_id=data.source_id,
            source_label=source_label,
        )
        earning = await self._repo.create_earning(
            user_id=user_id,
            transaction_id=None,
            source_id=data.source_id,
            source_type=source_type,
            source_label=source_label,
            amount=data.amount,
            currency=data.currency,
            date=data.date,
            notes=data.notes,
        )
        await self._emit_earning_recorded(earning)
        await self._db.commit()
        return await self._build_earning_response(user_id, earning)

    async def edit_earning(
        self,
        user_id: uuid.UUID,
        earning_id: uuid.UUID,
        data: EarningUpdate,
    ) -> EarningResponse:
        earning = await self._repo.get_earning(user_id, earning_id)
        if earning is None:
            raise EarningNotFoundError(f"Earning {earning_id} not found.")

        fields = data.model_dump(exclude_unset=True)
        source_id = fields.get("source_id", earning.source_id)
        source = await self._resolve_source(user_id, source_id) if source_id else None
        if source is not None:
            fields["source_type"] = fields.get("source_type") or source.type
            if "source_label" not in fields:
                fields["source_label"] = source.name
        else:
            fields["source_type"] = fields.get("source_type", earning.source_type)
            fields["source_label"] = fields.get("source_label", earning.source_label)
        self._validate_source_fields(
            source_type=fields["source_type"],
            source_id=source_id,
            source_label=fields.get("source_label"),
        )
        await self._repo.update_earning(earning, **fields)
        await self._db.commit()
        for key, value in fields.items():
            setattr(earning, key, value)
        return await self._build_earning_response(user_id, earning)

    async def classify_transaction(
        self,
        user_id: uuid.UUID,
        transaction_id: uuid.UUID,
        data: ClassifyTransactionRequest,
    ) -> None:
        existing = await self._repo.get_earning_by_transaction(user_id, transaction_id)
        if existing is not None and data.classification == "income":
            raise TransactionAlreadyClassifiedError(
                f"Transaction {transaction_id} already has an earning record."
            )
        if data.classification != "income":
            return

        source = await self._resolve_source(user_id, data.source_id)
        transaction = await self._repo.get_transaction_snapshot(user_id, transaction_id)
        if transaction is None:
            raise TransactionNotFoundError(f"Transaction {transaction_id} not found.")

        source_type = source.type if source is not None else data.source_type
        source_label = (
            source.name
            if source is not None
            else data.source_label or transaction.get("raw_description")
        )
        self._validate_source_fields(
            source_type=source_type,
            source_id=data.source_id,
            source_label=source_label,
        )
        earning = await self._repo.create_earning(
            user_id=user_id,
            transaction_id=transaction_id,
            source_id=data.source_id,
            source_type=source_type,
            source_label=source_label,
            amount=transaction["amount"],
            currency=transaction["currency"],
            date=transaction["date"],
            notes=data.notes,
        )
        await self._emit_earning_recorded(earning)
        await self._db.commit()

    async def list_earnings(
        self, user_id: uuid.UUID, filters: EarningFilters
    ) -> list[EarningResponse]:
        earnings = await self._repo.list_earnings(
            user_id=user_id,
            source_type=filters.source_type,
            date_from=filters.date_from,
            date_to=filters.date_to,
            source_id=filters.source_id,
        )
        return [
            await self._build_earning_response(user_id, earning) for earning in earnings
        ]

    async def handle_transaction_created(self, payload: dict[str, Any]) -> None:
        transaction_type = payload.get("type")
        if transaction_type == "transfer" or transaction_type != "credit":
            return

        user_id = uuid.UUID(str(payload["user_id"]))
        transaction_id = uuid.UUID(str(payload["transaction_id"]))
        existing = await self._repo.get_earning_by_transaction(user_id, transaction_id)
        if existing is not None:
            return

        description = payload.get("raw_description") or ""
        upper_description = description.upper()

        peer_names = await self._repo.list_peer_contact_names(user_id)
        if any(peer_name.upper() in upper_description for peer_name in peer_names):
            return

        sources = await self._repo.list_sources(user_id, active_only=True)
        recurring_source = await self._repo.find_recurring_source_match(
            user_id=user_id,
            amount=payload["amount"],
            earning_date=self._parse_date(payload["date"]),
        )
        matched_source = next(
            (source for source in sources if source.name.upper() in upper_description),
            None,
        )
        if matched_source is None:
            matched_source = recurring_source

        if matched_source is not None or any(
            keyword in upper_description for keyword in _INCOME_KEYWORDS
        ):
            earning = await self._repo.create_earning(
                user_id=user_id,
                transaction_id=transaction_id,
                source_id=matched_source.id if matched_source is not None else None,
                source_type=matched_source.type
                if matched_source is not None
                else "salary",
                source_label=matched_source.name
                if matched_source is not None
                else description,
                amount=payload["amount"],
                currency=payload["currency"],
                date=self._parse_date(payload["date"]),
                notes=None,
            )
            await self._emit_earning_recorded(earning)
            await self._db.commit()
            return

        event = EarningClassificationNeeded(
            transaction_id=transaction_id,
            user_id=user_id,
            amount=payload["amount"],
            currency=payload["currency"],
            description=description,
        )
        await self._repo.add_outbox_event(event.event_type, event.to_payload())
        await self._db.commit()

    async def _resolve_source(
        self,
        user_id: uuid.UUID,
        source_id: uuid.UUID | None,
    ) -> Any | None:
        if source_id is None:
            return None
        source = await self._repo.get_source(user_id, source_id)
        if source is None:
            raise EarningSourceNotFoundError(f"Earning source {source_id} not found.")
        return source

    async def _emit_earning_recorded(self, earning: Any) -> None:
        event = EarningRecorded(
            earning_id=earning.id,
            user_id=earning.user_id,
            source_type=earning.source_type,
            amount=earning.amount,
            currency=earning.currency,
            date=earning.date,
        )
        await self._repo.add_outbox_event(event.event_type, event.to_payload())

    async def _build_earning_response(
        self, user_id: uuid.UUID, earning: Any
    ) -> EarningResponse:
        source_name = None
        if earning.source_id is not None:
            source = await self._repo.get_source(user_id, earning.source_id)
            source_name = source.name if source is not None else earning.source_label
        return EarningResponse(
            id=earning.id,
            user_id=earning.user_id,
            transaction_id=earning.transaction_id,
            source_id=earning.source_id,
            source_type=earning.source_type,
            source_label=earning.source_label,
            source_name=source_name,
            amount=earning.amount,
            currency=earning.currency,
            date=earning.date,
            notes=earning.notes,
            created_at=earning.created_at,
            updated_at=earning.updated_at,
        )

    @staticmethod
    def _parse_date(value: Any) -> date:
        if isinstance(value, date):
            return value
        return date.fromisoformat(str(value))

    @staticmethod
    def _validate_source_fields(
        *,
        source_type: str | None,
        source_id: uuid.UUID | None,
        source_label: str | None,
    ) -> None:
        if source_type != "other" and source_id is None and not source_label:
            raise ValueError(
                "Either source_id or source_label is required unless source_type is 'other'."
            )
