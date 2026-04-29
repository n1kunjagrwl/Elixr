"""
Service-layer tests for the categorization domain.

All external dependencies (DB session, repository, ADK client) are mocked.
No real database or network connections are made.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tests.conftest import USER_ID, make_test_settings


# ── Helpers ────────────────────────────────────────────────────────────────────


def _make_service(mock_db):
    from elixir.domains.categorization.services import CategorizationService

    return CategorizationService(db=mock_db, settings=make_test_settings())


def _make_category(
    category_id=None,
    user_id=None,
    name="Food & Dining",
    slug="food-dining",
    kind="expense",
    icon=None,
    is_default=False,
    is_active=True,
    parent_id=None,
):
    cat = MagicMock()
    cat.id = category_id or uuid.uuid4()
    cat.user_id = user_id  # None = system default
    cat.name = name
    cat.slug = slug
    cat.kind = kind
    cat.icon = icon
    cat.is_default = is_default
    cat.is_active = is_active
    cat.parent_id = parent_id
    cat.created_at = datetime.now(timezone.utc)
    cat.updated_at = None
    return cat


def _make_rule(
    rule_id=None,
    user_id=None,
    pattern="zomato",
    match_type="contains",
    category_id=None,
    priority=0,
    is_active=True,
):
    rule = MagicMock()
    rule.id = rule_id or uuid.uuid4()
    rule.user_id = user_id or USER_ID
    rule.pattern = pattern
    rule.match_type = match_type
    rule.category_id = category_id or uuid.uuid4()
    rule.priority = priority
    rule.is_active = is_active
    rule.created_at = datetime.now(timezone.utc)
    rule.updated_at = None
    return rule


# ── list_categories tests ──────────────────────────────────────────────────────


class TestListCategories:
    async def test_list_categories_returns_defaults_and_user_custom(self, mock_db):
        """list_categories returns both system defaults and user custom categories."""
        svc = _make_service(mock_db)
        system_cat = _make_category(user_id=None, name="Food & Dining", is_default=True)
        user_cat = _make_category(user_id=USER_ID, name="My Custom", is_default=False)

        with patch.object(
            svc._repo,
            "get_categories_for_user",
            new=AsyncMock(return_value=[system_cat, user_cat]),
        ):
            results = await svc.list_categories(USER_ID)

        assert len(results) == 2
        names = {r.name for r in results}
        assert "Food & Dining" in names
        assert "My Custom" in names

    async def test_list_categories_new_user_sees_22_defaults(self, mock_db):
        """A new user with no custom categories sees exactly 22 system defaults."""
        svc = _make_service(mock_db)
        # Simulate 22 default categories returned by repo
        defaults = [
            _make_category(
                user_id=None, name=f"Default {i}", slug=f"default-{i}", is_default=True
            )
            for i in range(22)
        ]

        with patch.object(
            svc._repo, "get_categories_for_user", new=AsyncMock(return_value=defaults)
        ):
            results = await svc.list_categories(USER_ID)

        assert len(results) == 22


# ── create_category tests ──────────────────────────────────────────────────────


class TestCreateCategory:
    async def test_create_category_creates_row_and_outbox_event(self, mock_db):
        """Creating a category persists the row and writes a CategoryCreated outbox event."""
        from elixir.domains.categorization.schemas import CategoryCreate

        svc = _make_service(mock_db)
        cat = _make_category(
            user_id=USER_ID, name="My Food", slug="my-food", kind="expense"
        )
        outbox_events = []

        data = CategoryCreate(name="My Food", slug="my-food", kind="expense")

        with (
            patch.object(
                svc._repo,
                "get_category_by_slug_for_user",
                new=AsyncMock(return_value=None),
            ),
            patch.object(svc._repo, "create_category", new=AsyncMock(return_value=cat)),
            patch.object(
                svc._repo,
                "add_outbox_event",
                new=AsyncMock(side_effect=lambda et, p: outbox_events.append((et, p))),
            ),
        ):
            result = await svc.create_category(USER_ID, data)

        assert result.name == "My Food"
        assert result.slug == "my-food"
        mock_db.commit.assert_called_once()
        assert len(outbox_events) == 1
        event_type, payload = outbox_events[0]
        assert event_type == "categorization.CategoryCreated"
        assert payload["user_id"] == str(USER_ID)
        assert payload["name"] == "My Food"

    async def test_create_category_duplicate_slug_raises_409(self, mock_db):
        """Creating a category with a slug that already exists raises DuplicateSlugError."""
        from elixir.domains.categorization.schemas import CategoryCreate
        from elixir.shared.exceptions import DuplicateSlugError

        svc = _make_service(mock_db)
        existing_cat = _make_category(user_id=USER_ID, slug="food-dining")
        data = CategoryCreate(name="Food Again", slug="food-dining", kind="expense")

        with patch.object(
            svc._repo,
            "get_category_by_slug_for_user",
            new=AsyncMock(return_value=existing_cat),
        ):
            with pytest.raises(DuplicateSlugError):
                await svc.create_category(USER_ID, data)

    async def test_create_transfer_category_raises_forbidden(self, mock_db):
        """Users cannot create categories with kind='transfer' — raises CategoryKindForbiddenError."""
        from elixir.domains.categorization.schemas import CategoryCreate
        from elixir.shared.exceptions import CategoryKindForbiddenError

        svc = _make_service(mock_db)
        data = CategoryCreate(name="My Transfer", slug="my-transfer", kind="transfer")

        with pytest.raises(CategoryKindForbiddenError):
            await svc.create_category(USER_ID, data)


# ── update_category tests ──────────────────────────────────────────────────────


class TestUpdateCategory:
    async def test_update_category_updates_fields(self, mock_db):
        """Happy path: updating a user-owned, non-default category updates its fields."""
        from elixir.domains.categorization.schemas import CategoryUpdate

        svc = _make_service(mock_db)
        cat = _make_category(user_id=USER_ID, name="Old Name", is_default=False)

        data = CategoryUpdate(name="New Name", icon="🍔")

        with (
            patch.object(
                svc._repo, "get_category_by_id", new=AsyncMock(return_value=cat)
            ),
            patch.object(
                svc._repo, "update_category", new=AsyncMock(return_value=None)
            ),
        ):
            result = await svc.update_category(USER_ID, cat.id, data)

        assert result is not None
        mock_db.commit.assert_called_once()

    async def test_update_default_category_raises_forbidden(self, mock_db):
        """Cannot edit a system default category — raises CannotEditDefaultCategoryError."""
        from elixir.domains.categorization.schemas import CategoryUpdate
        from elixir.shared.exceptions import CannotEditDefaultCategoryError

        svc = _make_service(mock_db)
        default_cat = _make_category(
            user_id=None, name="Food & Dining", is_default=True
        )

        data = CategoryUpdate(name="Renamed")

        with patch.object(
            svc._repo, "get_category_by_id", new=AsyncMock(return_value=default_cat)
        ):
            with pytest.raises(CannotEditDefaultCategoryError):
                await svc.update_category(USER_ID, default_cat.id, data)

    async def test_update_category_not_found_raises_404(self, mock_db):
        """When category is not found, CategoryNotFoundError is raised."""
        from elixir.domains.categorization.schemas import CategoryUpdate
        from elixir.shared.exceptions import CategoryNotFoundError

        svc = _make_service(mock_db)

        with patch.object(
            svc._repo, "get_category_by_id", new=AsyncMock(return_value=None)
        ):
            with pytest.raises(CategoryNotFoundError):
                await svc.update_category(USER_ID, uuid.uuid4(), CategoryUpdate())


# ── list_rules tests ───────────────────────────────────────────────────────────


class TestListRules:
    async def test_list_rules_returns_rules_ordered_by_priority(self, mock_db):
        """list_rules returns rules in priority descending order."""
        svc = _make_service(mock_db)
        rule_high = _make_rule(priority=10, pattern="zomato")
        rule_low = _make_rule(priority=0, pattern="swiggy")

        with patch.object(
            svc._repo,
            "get_rules_for_user",
            new=AsyncMock(return_value=[rule_high, rule_low]),
        ):
            results = await svc.list_rules(USER_ID)

        assert len(results) == 2
        assert results[0].priority == 10
        assert results[1].priority == 0


# ── create_rule tests ──────────────────────────────────────────────────────────


class TestCreateRule:
    async def test_create_rule_with_valid_regex_succeeds(self, mock_db):
        """Creating a rule with a valid regex pattern succeeds."""
        from elixir.domains.categorization.schemas import RuleCreate

        svc = _make_service(mock_db)
        cat = _make_category(user_id=USER_ID)
        rule = _make_rule(pattern=r"zomato|swiggy", match_type="regex")
        data = RuleCreate(
            pattern=r"zomato|swiggy",
            match_type="regex",
            category_id=cat.id,
            priority=5,
        )

        with (
            patch.object(
                svc._repo, "get_category_by_id", new=AsyncMock(return_value=cat)
            ),
            patch.object(svc._repo, "create_rule", new=AsyncMock(return_value=rule)),
        ):
            result = await svc.create_rule(USER_ID, data)

        assert result is not None
        mock_db.commit.assert_called_once()

    async def test_create_rule_with_invalid_regex_raises_422(self, mock_db):
        """Creating a regex rule with an invalid pattern raises InvalidRegexPatternError."""
        from elixir.domains.categorization.schemas import RuleCreate
        from elixir.shared.exceptions import InvalidRegexPatternError

        svc = _make_service(mock_db)
        cat = _make_category(user_id=USER_ID)
        data = RuleCreate(
            pattern=r"[invalid(regex",
            match_type="regex",
            category_id=cat.id,
        )

        with patch.object(
            svc._repo, "get_category_by_id", new=AsyncMock(return_value=cat)
        ):
            with pytest.raises(InvalidRegexPatternError):
                await svc.create_rule(USER_ID, data)

    async def test_create_rule_with_nonexistent_category_raises_404(self, mock_db):
        """Creating a rule that references a non-existent category raises CategoryNotFoundError."""
        from elixir.domains.categorization.schemas import RuleCreate
        from elixir.shared.exceptions import CategoryNotFoundError

        svc = _make_service(mock_db)
        data = RuleCreate(
            pattern="zomato",
            match_type="contains",
            category_id=uuid.uuid4(),
        )

        with patch.object(
            svc._repo, "get_category_by_id", new=AsyncMock(return_value=None)
        ):
            with pytest.raises(CategoryNotFoundError):
                await svc.create_rule(USER_ID, data)


# ── update_rule tests ──────────────────────────────────────────────────────────


class TestUpdateRule:
    async def test_update_rule_updates_fields(self, mock_db):
        """Happy path: updating a rule updates specified fields."""
        from elixir.domains.categorization.schemas import RuleUpdate

        svc = _make_service(mock_db)
        rule = _make_rule(pattern="zomato", priority=0)
        data = RuleUpdate(priority=10)

        with (
            patch.object(svc._repo, "get_rule_by_id", new=AsyncMock(return_value=rule)),
            patch.object(svc._repo, "update_rule", new=AsyncMock(return_value=None)),
        ):
            result = await svc.update_rule(USER_ID, rule.id, data)

        assert result is not None
        mock_db.commit.assert_called_once()


# ── delete_rule tests ──────────────────────────────────────────────────────────


class TestDeleteRule:
    async def test_delete_rule_removes_rule(self, mock_db):
        """Deleting a rule removes it from the database."""
        svc = _make_service(mock_db)
        rule = _make_rule()

        with (
            patch.object(svc._repo, "get_rule_by_id", new=AsyncMock(return_value=rule)),
            patch.object(svc._repo, "delete_rule", new=AsyncMock(return_value=None)),
        ):
            await svc.delete_rule(USER_ID, rule.id)

        mock_db.commit.assert_called_once()


# ── suggest_category tests ─────────────────────────────────────────────────────


class TestSuggestCategory:
    async def test_suggest_category_transfer_type_returns_self_transfer(self, mock_db):
        """If transaction_type='transfer', immediately return Self Transfer with confidence=1.0."""
        svc = _make_service(mock_db)
        self_transfer_cat = _make_category(
            user_id=None,
            name="Self Transfer",
            slug="self-transfer",
            kind="transfer",
            is_default=True,
        )

        with patch.object(
            svc._repo,
            "get_default_category_by_slug",
            new=AsyncMock(return_value=self_transfer_cat),
        ):
            result = await svc.suggest_category(
                description="Transfer to savings",
                user_id=USER_ID,
                amount=1000.0,
                transaction_type="transfer",
            )

        assert result.confidence == 1.0
        assert result.source == "rule"
        assert result.category_name == "Self Transfer"

    async def test_suggest_category_rule_match_returns_confidence_1(self, mock_db):
        """If a rule matches, return confidence=1.0 and source='rule' without calling ADK."""
        svc = _make_service(mock_db)
        cat_id = uuid.uuid4()
        rule = _make_rule(pattern="ZOMATO", match_type="contains", category_id=cat_id)
        cat = _make_category(category_id=cat_id, name="Food & Dining", kind="expense")

        with (
            patch.object(
                svc._repo, "find_matching_rule", new=AsyncMock(return_value=rule)
            ),
            patch.object(
                svc._repo, "get_category_by_id", new=AsyncMock(return_value=cat)
            ),
        ):
            result = await svc.suggest_category(
                description="ZOMATO ORDER",
                user_id=USER_ID,
                amount=500.0,
                transaction_type="expense",
            )

        assert result.confidence == 1.0
        assert result.source == "rule"
        assert result.category_id == cat_id

    async def test_suggest_category_rule_contains_match(self, mock_db):
        """'contains' match_type correctly matches when pattern is substring of description."""
        svc = _make_service(mock_db)
        cat_id = uuid.uuid4()
        rule = _make_rule(pattern="zomato", match_type="contains", category_id=cat_id)
        cat = _make_category(category_id=cat_id, name="Food & Dining")

        with (
            patch.object(
                svc._repo, "find_matching_rule", new=AsyncMock(return_value=rule)
            ),
            patch.object(
                svc._repo, "get_category_by_id", new=AsyncMock(return_value=cat)
            ),
        ):
            result = await svc.suggest_category(
                description="Payment to ZOMATO",
                user_id=USER_ID,
                amount=300.0,
            )

        assert result.confidence == 1.0
        assert result.source == "rule"

    async def test_suggest_category_rule_starts_with_match(self, mock_db):
        """'starts_with' match_type correctly matches when description starts with pattern."""
        svc = _make_service(mock_db)
        cat_id = uuid.uuid4()
        rule = _make_rule(
            pattern="amazon", match_type="starts_with", category_id=cat_id
        )
        cat = _make_category(category_id=cat_id, name="Shopping")

        with (
            patch.object(
                svc._repo, "find_matching_rule", new=AsyncMock(return_value=rule)
            ),
            patch.object(
                svc._repo, "get_category_by_id", new=AsyncMock(return_value=cat)
            ),
        ):
            result = await svc.suggest_category(
                description="Amazon purchase",
                user_id=USER_ID,
                amount=500.0,
            )

        assert result.confidence == 1.0
        assert result.source == "rule"

    async def test_suggest_category_rule_exact_match(self, mock_db):
        """'exact' match_type correctly matches only the exact description."""
        svc = _make_service(mock_db)
        cat_id = uuid.uuid4()
        rule = _make_rule(
            pattern="netflix subscription", match_type="exact", category_id=cat_id
        )
        cat = _make_category(category_id=cat_id, name="Subscriptions")

        with (
            patch.object(
                svc._repo, "find_matching_rule", new=AsyncMock(return_value=rule)
            ),
            patch.object(
                svc._repo, "get_category_by_id", new=AsyncMock(return_value=cat)
            ),
        ):
            result = await svc.suggest_category(
                description="Netflix Subscription",
                user_id=USER_ID,
                amount=649.0,
            )

        assert result.confidence == 1.0
        assert result.source == "rule"

    async def test_suggest_category_rule_regex_match(self, mock_db):
        """'regex' match_type correctly matches via re.search with IGNORECASE."""
        svc = _make_service(mock_db)
        cat_id = uuid.uuid4()
        rule = _make_rule(
            pattern=r"zomato|swiggy", match_type="regex", category_id=cat_id
        )
        cat = _make_category(category_id=cat_id, name="Food & Dining")

        with (
            patch.object(
                svc._repo, "find_matching_rule", new=AsyncMock(return_value=rule)
            ),
            patch.object(
                svc._repo, "get_category_by_id", new=AsyncMock(return_value=cat)
            ),
        ):
            result = await svc.suggest_category(
                description="SWIGGY ORDER 12345",
                user_id=USER_ID,
                amount=250.0,
            )

        assert result.confidence == 1.0
        assert result.source == "rule"

    async def test_suggest_category_no_rule_calls_adk(self, mock_db):
        """When no rule matches, returns CategorySuggestion with source='none' if adk_client is None."""
        svc = _make_service(mock_db)

        with patch.object(
            svc._repo, "find_matching_rule", new=AsyncMock(return_value=None)
        ):
            result = await svc.suggest_category(
                description="Unknown transaction XYZ",
                user_id=USER_ID,
                amount=100.0,
                adk_client=None,
            )

        assert result.source == "none"
        assert result.confidence == 0.0
        assert result.category_id is None
