import re
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from elixir.domains.categorization.models import (
    CategorizationOutbox,
    CategorizationRule,
    Category,
)


class CategorizationRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    # ── Categories ────────────────────────────────────────────────────────────

    async def get_categories_for_user(self, user_id: uuid.UUID) -> list[Category]:
        """
        Query the categories_for_user view.
        CRITICAL: filter uses WHERE user_id = :uid OR user_id IS NULL to
        include both user-specific categories and system defaults.
        """
        result = await self._db.execute(
            text(
                "SELECT id, user_id, name, slug, kind, icon, is_default, "
                "is_active, parent_id, created_at, updated_at "
                "FROM categories_for_user "
                "WHERE user_id = :uid OR user_id IS NULL"
            ),
            {"uid": str(user_id)},
        )
        rows = result.mappings().all()
        # Hydrate into Category-like objects using ORM select
        if not rows:
            return []
        # Return raw ORM objects from the underlying table instead
        # (view is for cross-domain reads; within domain we query the table)
        orm_result = await self._db.execute(
            select(Category).where(
                (Category.user_id == user_id) | (Category.user_id.is_(None)),
                Category.is_active.is_(True),
            )
        )
        return list(orm_result.scalars().all())

    async def get_category_by_id(self, category_id: uuid.UUID) -> Category | None:
        result = await self._db.execute(
            select(Category).where(Category.id == category_id)
        )
        return result.scalar_one_or_none()

    async def get_category_by_slug_for_user(
        self, slug: str, user_id: uuid.UUID
    ) -> Category | None:
        result = await self._db.execute(
            select(Category).where(
                Category.slug == slug,
                Category.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_default_category_by_slug(self, slug: str) -> Category | None:
        result = await self._db.execute(
            select(Category).where(
                Category.slug == slug,
                Category.user_id.is_(None),
                Category.is_default.is_(True),
            )
        )
        return result.scalar_one_or_none()

    async def create_category(self, **fields: Any) -> Category:
        cat = Category(**fields)
        self._db.add(cat)
        await self._db.flush()
        return cat

    async def update_category(self, category: Category, **fields: Any) -> None:
        for key, value in fields.items():
            setattr(category, key, value)
        category.updated_at = datetime.now(timezone.utc)

    # ── Rules ─────────────────────────────────────────────────────────────────

    async def get_rules_for_user(self, user_id: uuid.UUID) -> list[CategorizationRule]:
        result = await self._db.execute(
            select(CategorizationRule)
            .where(CategorizationRule.user_id == user_id)
            .order_by(CategorizationRule.priority.desc())
        )
        return list(result.scalars().all())

    async def get_rule_by_id(
        self, user_id: uuid.UUID, rule_id: uuid.UUID
    ) -> CategorizationRule | None:
        result = await self._db.execute(
            select(CategorizationRule).where(
                CategorizationRule.id == rule_id,
                CategorizationRule.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    async def create_rule(self, **fields: Any) -> CategorizationRule:
        rule = CategorizationRule(**fields)
        self._db.add(rule)
        await self._db.flush()
        return rule

    async def update_rule(self, rule: CategorizationRule, **fields: Any) -> None:
        for key, value in fields.items():
            setattr(rule, key, value)
        rule.updated_at = datetime.now(timezone.utc)

    async def delete_rule(self, rule: CategorizationRule) -> None:
        await self._db.delete(rule)

    async def find_matching_rule(
        self, user_id: uuid.UUID, description: str
    ) -> CategorizationRule | None:
        """
        Apply rules in priority DESC order and return the first matching rule.
        Rule matching logic:
          - contains:    pattern.lower() in description.lower()
          - starts_with: description.lower().startswith(pattern.lower())
          - exact:       description.lower() == pattern.lower()
          - regex:       re.search(pattern, description, re.IGNORECASE)
        """
        rules = await self.get_rules_for_user(user_id)
        for rule in rules:
            if not rule.is_active:
                continue
            matched = False
            if rule.match_type == "contains":
                matched = rule.pattern.lower() in description.lower()
            elif rule.match_type == "starts_with":
                matched = description.lower().startswith(rule.pattern.lower())
            elif rule.match_type == "exact":
                matched = description.lower() == rule.pattern.lower()
            elif rule.match_type == "regex":
                matched = bool(re.search(rule.pattern, description, re.IGNORECASE))
            if matched:
                return rule
        return None

    # ── Outbox ────────────────────────────────────────────────────────────────

    async def add_outbox_event(self, event_type: str, payload: dict[str, Any]) -> None:
        row = CategorizationOutbox(event_type=event_type, payload=payload)
        self._db.add(row)
