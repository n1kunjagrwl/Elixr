from __future__ import annotations

import re
import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from elixir.domains.categorization.events import CategoryCreated
from elixir.domains.categorization.repositories import CategorizationRepository
from elixir.domains.categorization.schemas import (
    CategoryCreate,
    CategoryResponse,
    CategorySuggestion,
    CategoryUpdate,
    RuleCreate,
    RuleResponse,
    RuleUpdate,
)
from elixir.shared.config import Settings
from elixir.shared.exceptions import (
    CannotEditDefaultCategoryError,
    CategoryKindForbiddenError,
    CategoryNotFoundError,
    DuplicateSlugError,
    InvalidRegexPatternError,
    RuleNotFoundError,
)


class CategorizationService:
    def __init__(self, db: AsyncSession, settings: Settings) -> None:
        self._db = db
        self._repo = CategorizationRepository(db)
        self._settings = settings

    # ── Categories ────────────────────────────────────────────────────────────

    async def list_categories(self, user_id: uuid.UUID) -> list[CategoryResponse]:
        categories = await self._repo.get_categories_for_user(user_id)
        return [CategoryResponse.model_validate(c) for c in categories]

    async def create_category(
        self, user_id: uuid.UUID, data: CategoryCreate
    ) -> CategoryResponse:
        # Users cannot create transfer categories
        if data.kind == "transfer":
            raise CategoryKindForbiddenError(
                "Users cannot create categories with kind='transfer'."
            )

        # Check for duplicate slug (scoped to this user)
        existing = await self._repo.get_category_by_slug_for_user(data.slug, user_id)
        if existing is not None:
            raise DuplicateSlugError(
                f"A category with slug '{data.slug}' already exists."
            )

        cat = await self._repo.create_category(
            user_id=user_id,
            name=data.name,
            slug=data.slug,
            kind=data.kind,
            icon=data.icon,
            parent_id=data.parent_id,
            is_default=False,
            is_active=True,
        )

        # Write CategoryCreated event to outbox in same transaction
        event = CategoryCreated(
            category_id=str(cat.id),
            user_id=str(user_id),
            name=cat.name,
            kind=cat.kind,
        )
        await self._repo.add_outbox_event(event.event_type, event.to_payload())

        await self._db.commit()
        return CategoryResponse.model_validate(cat)

    async def update_category(
        self, user_id: uuid.UUID, category_id: uuid.UUID, data: CategoryUpdate
    ) -> CategoryResponse:
        cat = await self._repo.get_category_by_id(category_id)
        if cat is None:
            raise CategoryNotFoundError(f"Category {category_id} not found.")
        if cat.is_default:
            raise CannotEditDefaultCategoryError(
                "System default categories cannot be edited."
            )

        update_fields = data.model_dump(exclude_unset=True)
        if update_fields:
            await self._repo.update_category(cat, **update_fields)

        await self._db.commit()
        return CategoryResponse.model_validate(cat)

    # ── Rules ─────────────────────────────────────────────────────────────────

    async def list_rules(self, user_id: uuid.UUID) -> list[RuleResponse]:
        rules = await self._repo.get_rules_for_user(user_id)
        return [RuleResponse.model_validate(r) for r in rules]

    async def create_rule(
        self, user_id: uuid.UUID, data: RuleCreate
    ) -> RuleResponse:
        # Validate that the referenced category exists
        cat = await self._repo.get_category_by_id(data.category_id)
        if cat is None:
            raise CategoryNotFoundError(
                f"Category {data.category_id} not found."
            )

        # Validate regex pattern if match_type is regex
        if data.match_type == "regex":
            try:
                re.compile(data.pattern)
            except re.error as exc:
                raise InvalidRegexPatternError(
                    f"Invalid regex pattern '{data.pattern}': {exc}"
                ) from exc

        rule = await self._repo.create_rule(
            user_id=user_id,
            pattern=data.pattern,
            match_type=data.match_type,
            category_id=data.category_id,
            priority=data.priority,
            is_active=True,
        )
        await self._db.commit()
        return RuleResponse.model_validate(rule)

    async def update_rule(
        self, user_id: uuid.UUID, rule_id: uuid.UUID, data: RuleUpdate
    ) -> RuleResponse:
        rule = await self._repo.get_rule_by_id(user_id, rule_id)
        if rule is None:
            raise RuleNotFoundError(f"Rule {rule_id} not found.")

        update_fields = data.model_dump(exclude_unset=True)

        # Validate regex pattern if match_type or pattern changes
        new_match_type = update_fields.get("match_type", rule.match_type)
        new_pattern = update_fields.get("pattern", rule.pattern)
        if new_match_type == "regex":
            try:
                re.compile(new_pattern)
            except re.error as exc:
                raise InvalidRegexPatternError(
                    f"Invalid regex pattern '{new_pattern}': {exc}"
                ) from exc

        if update_fields:
            await self._repo.update_rule(rule, **update_fields)

        await self._db.commit()
        return RuleResponse.model_validate(rule)

    async def delete_rule(self, user_id: uuid.UUID, rule_id: uuid.UUID) -> None:
        rule = await self._repo.get_rule_by_id(user_id, rule_id)
        if rule is None:
            raise RuleNotFoundError(f"Rule {rule_id} not found.")
        await self._repo.delete_rule(rule)
        await self._db.commit()

    # ── Suggest Category ──────────────────────────────────────────────────────

    async def suggest_category(
        self,
        description: str,
        user_id: uuid.UUID,
        amount: float,
        transaction_type: str | None = None,
        adk_client: Any | None = None,
    ) -> CategorySuggestion:
        """
        Resolution order:
        1. If transaction_type == 'transfer': return Self Transfer, confidence=1.0
        2. Check user's categorization_rules (priority DESC) — rule match → confidence=1.0
        3. Call ADK client (injected) if provided
        4. Fallback: CategorySuggestion with confidence=0.0, source='none'
        """
        # Step 1: Transfer shortcut
        if transaction_type == "transfer":
            self_transfer = await self._repo.get_default_category_by_slug("self-transfer")
            cat_id = self_transfer.id if self_transfer else None
            cat_name = self_transfer.name if self_transfer else "Self Transfer"
            return CategorySuggestion(
                category_id=cat_id,
                category_name=cat_name,
                confidence=1.0,
                source="rule",
            )

        # Step 2: User rules
        rule = await self._repo.find_matching_rule(user_id, description)
        if rule is not None:
            cat = await self._repo.get_category_by_id(rule.category_id)
            return CategorySuggestion(
                category_id=rule.category_id,
                category_name=cat.name if cat else None,
                confidence=1.0,
                source="rule",
            )

        # Step 3: ADK client
        if adk_client is not None:
            try:
                adk_result = await adk_client.classify(
                    description=description,
                    amount=amount,
                    user_id=str(user_id),
                )
                if adk_result:
                    return CategorySuggestion(
                        category_id=adk_result.get("category_id"),
                        category_name=adk_result.get("category_name"),
                        confidence=adk_result.get("confidence", 0.5),
                        source="ai",
                        item_suggestions=adk_result.get("item_suggestions", []),
                    )
            except Exception:
                pass

        # Step 4: Fallback
        return CategorySuggestion(
            category_id=None,
            category_name=None,
            confidence=0.0,
            source="none",
        )
