"""
Service-layer tests for the notifications domain.

All external dependencies (DB session, repository) are mocked.
No real database or network connections are made.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tests.conftest import USER_ID


# ── Helpers ────────────────────────────────────────────────────────────────────


def _make_service(mock_db):
    from elixir.domains.notifications.services import NotificationsService

    return NotificationsService(db=mock_db)


def _make_notification(
    notification_id=None,
    user_id=None,
    type_="accounts.AccountLinked",
    title="Account added",
    body="Upload a statement to start tracking.",
    route="/statements/upload",
    primary_entity_id=None,
    secondary_entity_id=None,
    period_start=None,
    read_at=None,
):
    n = MagicMock()
    n.id = notification_id or uuid.uuid4()
    n.user_id = user_id or USER_ID
    n.type = type_
    n.title = title
    n.body = body
    n.route = route
    n.primary_entity_id = primary_entity_id or uuid.uuid4()
    n.secondary_entity_id = secondary_entity_id
    n.period_start = period_start
    n.read_at = read_at
    n.created_at = datetime.now(timezone.utc)
    return n


# ── TestListNotifications ──────────────────────────────────────────────────────


class TestListNotifications:
    async def test_list_all(self, mock_db):
        """list_notifications returns all notifications for user."""

        svc = _make_service(mock_db)
        notifications = [_make_notification(), _make_notification()]

        with patch.object(
            svc._repo, "list_notifications", new=AsyncMock(return_value=notifications)
        ):
            results = await svc.list_notifications(USER_ID)

        assert len(results) == 2

    async def test_list_unread_only(self, mock_db):
        """list_notifications with unread_only=True filters to unread."""
        svc = _make_service(mock_db)
        unread = _make_notification(read_at=None)

        mock_list = AsyncMock(return_value=[unread])
        with patch.object(svc._repo, "list_notifications", new=mock_list):
            results = await svc.list_notifications(USER_ID, unread_only=True)

        mock_list.assert_called_once_with(
            USER_ID, unread_only=True, page=1, page_size=20
        )
        assert len(results) == 1

    async def test_list_pagination(self, mock_db):
        """page/page_size are forwarded to the repository."""
        svc = _make_service(mock_db)

        mock_list = AsyncMock(return_value=[])
        with patch.object(svc._repo, "list_notifications", new=mock_list):
            await svc.list_notifications(USER_ID, page=3, page_size=10)

        mock_list.assert_called_once_with(
            USER_ID, unread_only=False, page=3, page_size=10
        )


# ── TestMarkRead ───────────────────────────────────────────────────────────────


class TestMarkRead:
    async def test_mark_read_sets_read_at(self, mock_db):
        """mark_read calls repo.mark_read when notification is found and unread."""
        svc = _make_service(mock_db)
        notification = _make_notification(read_at=None)
        notification_id = notification.id

        mock_get = AsyncMock(return_value=notification)
        mock_mark = AsyncMock(return_value=None)

        with (
            patch.object(svc._repo, "get_notification", new=mock_get),
            patch.object(svc._repo, "mark_read", new=mock_mark),
        ):
            await svc.mark_read(USER_ID, notification_id)

        mock_mark.assert_called_once_with(notification)

    async def test_mark_read_not_found(self, mock_db):
        """mark_read raises NotificationNotFoundError when notification is missing."""
        from elixir.shared.exceptions import NotificationNotFoundError

        svc = _make_service(mock_db)

        with patch.object(
            svc._repo, "get_notification", new=AsyncMock(return_value=None)
        ):
            with pytest.raises(NotificationNotFoundError):
                await svc.mark_read(USER_ID, uuid.uuid4())

    async def test_mark_read_already_read_is_noop(self, mock_db):
        """mark_read is a no-op (no error) if notification is already read."""
        svc = _make_service(mock_db)
        already_read = _make_notification(read_at=datetime.now(timezone.utc))

        mock_get = AsyncMock(return_value=already_read)
        mock_mark = AsyncMock(return_value=None)

        with (
            patch.object(svc._repo, "get_notification", new=mock_get),
            patch.object(svc._repo, "mark_read", new=mock_mark),
        ):
            # Should not raise
            await svc.mark_read(USER_ID, already_read.id)

        # mark_read on repo is still called — it handles the no-op internally
        mock_mark.assert_called_once_with(already_read)


# ── TestMarkAllRead ────────────────────────────────────────────────────────────


class TestMarkAllRead:
    async def test_mark_all_read_returns_count(self, mock_db):
        """mark_all_read returns dict with count of rows updated."""
        svc = _make_service(mock_db)

        with patch.object(svc._repo, "mark_all_read", new=AsyncMock(return_value=5)):
            result = await svc.mark_all_read(USER_ID)

        assert result == {"marked": 5}


# ── TestIdempotency ────────────────────────────────────────────────────────────


class TestIdempotency:
    async def test_create_if_not_exists_skips_duplicate(self, mock_db):
        """When notification_exists returns True, create_notification is NOT called."""
        svc = _make_service(mock_db)

        mock_exists = AsyncMock(return_value=True)
        mock_create = AsyncMock(return_value=_make_notification())

        with (
            patch.object(svc._repo, "notification_exists", new=mock_exists),
            patch.object(svc._repo, "create_notification", new=mock_create),
        ):
            await svc._create_if_not_exists(
                user_id=USER_ID,
                type_="accounts.AccountLinked",
                title="Account added",
                body="Some body.",
                route="/statements/upload",
                primary_entity_id=uuid.uuid4(),
            )

        mock_create.assert_not_called()

    async def test_create_if_not_exists_inserts_when_new(self, mock_db):
        """When notification_exists returns False, create_notification IS called."""
        svc = _make_service(mock_db)

        mock_exists = AsyncMock(return_value=False)
        mock_create = AsyncMock(return_value=_make_notification())

        with (
            patch.object(svc._repo, "notification_exists", new=mock_exists),
            patch.object(svc._repo, "create_notification", new=mock_create),
        ):
            await svc._create_if_not_exists(
                user_id=USER_ID,
                type_="accounts.AccountLinked",
                title="Account added",
                body="Some body.",
                route="/statements/upload",
                primary_entity_id=uuid.uuid4(),
            )

        mock_create.assert_called_once()


# ── TestEventHandlers ──────────────────────────────────────────────────────────


class TestEventHandlers:
    async def test_account_linked_creates_notification(self, mock_db):
        """handle_account_linked with valid payload creates a notification."""
        from elixir.domains.notifications.events import handle_account_linked

        account_id = uuid.uuid4()
        payload = {
            "user_id": str(USER_ID),
            "account_id": str(account_id),
            "nickname": "HDFC Savings",
        }

        mock_exists = AsyncMock(return_value=False)
        mock_create = AsyncMock(return_value=_make_notification())
        mock_commit = AsyncMock(return_value=None)
        mock_db.commit = mock_commit

        with patch(
            "elixir.domains.notifications.services.NotificationsRepository"
        ) as MockRepo:
            instance = MockRepo.return_value
            instance.notification_exists = mock_exists
            instance.create_notification = mock_create

            await handle_account_linked(payload, mock_db)

        mock_create.assert_called_once()

    async def test_budget_limit_warning_idempotent(self, mock_db):
        """Calling handle_budget_limit_warning twice with same goal_id+period_start creates only one notification."""
        from elixir.domains.notifications.events import handle_budget_limit_warning

        goal_id = uuid.uuid4()
        payload = {
            "user_id": str(USER_ID),
            "goal_id": str(goal_id),
            "percent_used": 85,
            "period_start": "2026-04-01",
            "current_spend": "8500.00",
            "limit_amount": "10000.00",
            "currency": "INR",
        }

        create_calls = []

        async def fake_exists(
            user_id,
            type_,
            primary_entity_id=None,
            secondary_entity_id=None,
            period_start=None,
        ):
            # Returns True on second call (simulating duplicate)
            return len(create_calls) > 0

        async def fake_create(**kwargs):
            create_calls.append(kwargs)
            return _make_notification()

        mock_db.commit = AsyncMock(return_value=None)

        with patch(
            "elixir.domains.notifications.services.NotificationsRepository"
        ) as MockRepo:
            instance = MockRepo.return_value
            instance.notification_exists = AsyncMock(side_effect=fake_exists)
            instance.create_notification = AsyncMock(side_effect=fake_create)

            await handle_budget_limit_warning(payload, mock_db)
            await handle_budget_limit_warning(payload, mock_db)

        # Only one notification should be created
        assert len(create_calls) == 1

    async def test_sip_detected_uses_both_ids(self, mock_db):
        """SIPDetected handler passes primary_entity_id=transaction_id and secondary_entity_id=sip_registration_id."""
        from elixir.domains.notifications.events import handle_sip_detected

        transaction_id = uuid.uuid4()
        sip_registration_id = uuid.uuid4()
        payload = {
            "user_id": str(USER_ID),
            "transaction_id": str(transaction_id),
            "sip_registration_id": str(sip_registration_id),
            "instrument_name": "Axis Bluechip Fund",
            "amount": "5000.00",
            "currency": "INR",
        }

        mock_exists = AsyncMock(return_value=False)
        captured_kwargs: dict = {}

        async def fake_create(**kwargs):
            captured_kwargs.update(kwargs)
            return _make_notification()

        mock_db.commit = AsyncMock(return_value=None)

        with patch(
            "elixir.domains.notifications.services.NotificationsRepository"
        ) as MockRepo:
            instance = MockRepo.return_value
            instance.notification_exists = mock_exists
            instance.create_notification = AsyncMock(side_effect=fake_create)

            await handle_sip_detected(payload, mock_db)

        assert captured_kwargs.get("primary_entity_id") == transaction_id
        assert captured_kwargs.get("secondary_entity_id") == sip_registration_id
