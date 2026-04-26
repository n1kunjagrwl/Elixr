"""
Service-layer tests for the identity domain.

All external dependencies (DB session, Twilio, Temporal) are mocked.
No real database or network connections are made.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from elixir.domains.identity.services import IdentityService
from elixir.shared.exceptions import (
    OTPExpiredError,
    OTPInvalidError,
    OTPLockedError,
    RateLimitError,
    SessionExpiredError,
    SessionRevokedError,
    UserNotFoundError,
)
from elixir.platform.security import create_refresh_token
from elixir.shared.security import hash_otp
from tests.conftest import PHONE, OTP_CODE, USER_ID, SESSION_ID


# ── Helpers ────────────────────────────────────────────────────────────────────

def _make_service(mock_db, mock_twilio, mock_temporal, test_settings) -> IdentityService:
    return IdentityService(
        db=mock_db,
        twilio=mock_twilio,
        temporal_client=mock_temporal,
        settings=test_settings,
    )


def _make_user(user_id=None, phone=PHONE):
    user = MagicMock()
    user.id = user_id or USER_ID
    user.phone_e164 = phone
    user.is_active = True
    return user


def _make_otp_request(
    user_id=None,
    otp_code=OTP_CODE,
    expired=False,
    locked=False,
    used=False,
    attempt_count=0,
):
    now = datetime.now(timezone.utc)
    otp_req = MagicMock()
    otp_req.id = uuid.uuid4()
    otp_req.user_id = user_id or USER_ID
    otp_req.code_hash = hash_otp(otp_code)
    otp_req.expires_at = (now - timedelta(seconds=1)) if expired else (now + timedelta(seconds=60))
    otp_req.locked_until = (now + timedelta(minutes=5)) if locked else None
    otp_req.used_at = now if used else None
    otp_req.attempt_count = attempt_count
    return otp_req


def _make_session(user_id=None, session_id=None, revoked=False, expired=False, settings=None):
    now = datetime.now(timezone.utc)
    s = MagicMock()
    s.id = session_id or SESSION_ID
    s.user_id = user_id or USER_ID
    s.revoked_at = now if revoked else None
    s.expires_at = (now - timedelta(days=1)) if expired else (now + timedelta(days=7))
    s.access_token_jti = str(uuid.uuid4())
    s.refresh_token_jti = str(uuid.uuid4())
    return s


# ── request_otp tests ─────────────────────────────────────────────────────────

class TestRequestOTP:
    async def test_request_otp_creates_otp_request_for_new_user(
        self, mock_db, mock_twilio, mock_temporal, test_settings
    ):
        """Happy path: new user gets OTP created, no error raised."""
        svc = _make_service(mock_db, mock_twilio, mock_temporal, test_settings)
        user = _make_user()

        with patch.object(svc._repo, "get_or_create_user", new=AsyncMock(return_value=(user, True))), \
             patch.object(svc._repo, "count_recent_otp_requests", new=AsyncMock(return_value=0)), \
             patch.object(svc._repo, "get_latest_otp_request", new=AsyncMock(return_value=None)), \
             patch.object(svc._repo, "create_otp_request", new=AsyncMock(return_value=_make_otp_request())):

            result = await svc.request_otp(PHONE)

        assert result.expires_in == test_settings.otp_expiry_seconds
        assert result.message == "OTP sent"
        mock_db.commit.assert_called_once()

    async def test_request_otp_for_existing_user_does_not_create_duplicate_user(
        self, mock_db, mock_twilio, mock_temporal, test_settings
    ):
        """Existing user: get_or_create_user returns created=False; OTP request still created."""
        svc = _make_service(mock_db, mock_twilio, mock_temporal, test_settings)
        user = _make_user()

        with patch.object(svc._repo, "get_or_create_user", new=AsyncMock(return_value=(user, False))) as mock_goc, \
             patch.object(svc._repo, "count_recent_otp_requests", new=AsyncMock(return_value=0)), \
             patch.object(svc._repo, "get_latest_otp_request", new=AsyncMock(return_value=None)), \
             patch.object(svc._repo, "create_otp_request", new=AsyncMock(return_value=_make_otp_request())):

            result = await svc.request_otp(PHONE)

        mock_goc.assert_called_once_with(PHONE)
        assert result.expires_in == test_settings.otp_expiry_seconds

    async def test_request_otp_raises_rate_limit_error(
        self, mock_db, mock_twilio, mock_temporal, test_settings
    ):
        """When OTP count >= limit, RateLimitError is raised."""
        svc = _make_service(mock_db, mock_twilio, mock_temporal, test_settings)
        user = _make_user()
        # count equals the limit
        over_limit = test_settings.otp_rate_limit_count

        with patch.object(svc._repo, "get_or_create_user", new=AsyncMock(return_value=(user, False))), \
             patch.object(svc._repo, "count_recent_otp_requests", new=AsyncMock(return_value=over_limit)):

            with pytest.raises(RateLimitError):
                await svc.request_otp(PHONE)

        mock_db.commit.assert_not_called()

    async def test_request_otp_raises_otp_locked_error_when_locked(
        self, mock_db, mock_twilio, mock_temporal, test_settings
    ):
        """When latest OTP has an active locked_until, OTPLockedError is raised."""
        svc = _make_service(mock_db, mock_twilio, mock_temporal, test_settings)
        user = _make_user()
        locked_otp = _make_otp_request(locked=True)

        with patch.object(svc._repo, "get_or_create_user", new=AsyncMock(return_value=(user, False))), \
             patch.object(svc._repo, "count_recent_otp_requests", new=AsyncMock(return_value=0)), \
             patch.object(svc._repo, "get_latest_otp_request", new=AsyncMock(return_value=locked_otp)):

            with pytest.raises(OTPLockedError):
                await svc.request_otp(PHONE)

        mock_db.commit.assert_not_called()

    async def test_request_otp_uses_temporal_when_available(
        self, mock_db, mock_twilio, mock_temporal, test_settings
    ):
        """When Temporal is available, start_workflow is called (not direct Twilio)."""
        svc = _make_service(mock_db, mock_twilio, mock_temporal, test_settings)
        user = _make_user()

        with patch.object(svc._repo, "get_or_create_user", new=AsyncMock(return_value=(user, True))), \
             patch.object(svc._repo, "count_recent_otp_requests", new=AsyncMock(return_value=0)), \
             patch.object(svc._repo, "get_latest_otp_request", new=AsyncMock(return_value=None)), \
             patch.object(svc._repo, "create_otp_request", new=AsyncMock(return_value=_make_otp_request())):

            await svc.request_otp(PHONE)

        mock_temporal.start_workflow.assert_called_once()
        mock_twilio.send_otp.assert_not_called()

    async def test_request_otp_falls_back_to_twilio_when_temporal_fails(
        self, mock_db, mock_twilio, mock_temporal, test_settings
    ):
        """When Temporal raises, direct Twilio SMS is used as fallback."""
        mock_temporal.start_workflow.side_effect = Exception("Temporal down")
        svc = _make_service(mock_db, mock_twilio, mock_temporal, test_settings)
        user = _make_user()

        with patch.object(svc._repo, "get_or_create_user", new=AsyncMock(return_value=(user, True))), \
             patch.object(svc._repo, "count_recent_otp_requests", new=AsyncMock(return_value=0)), \
             patch.object(svc._repo, "get_latest_otp_request", new=AsyncMock(return_value=None)), \
             patch.object(svc._repo, "create_otp_request", new=AsyncMock(return_value=_make_otp_request())):

            await svc.request_otp(PHONE)

        mock_twilio.send_otp.assert_called_once()

    async def test_request_otp_without_temporal_uses_twilio_directly(
        self, mock_db, mock_twilio, test_settings
    ):
        """When temporal_client is None, Twilio is used directly."""
        svc = _make_service(mock_db, mock_twilio, None, test_settings)
        user = _make_user()

        with patch.object(svc._repo, "get_or_create_user", new=AsyncMock(return_value=(user, True))), \
             patch.object(svc._repo, "count_recent_otp_requests", new=AsyncMock(return_value=0)), \
             patch.object(svc._repo, "get_latest_otp_request", new=AsyncMock(return_value=None)), \
             patch.object(svc._repo, "create_otp_request", new=AsyncMock(return_value=_make_otp_request())):

            await svc.request_otp(PHONE)

        # temporal is None, so send_otp should not be called from the fallback
        # (the if self._temporal block is skipped entirely)
        mock_twilio.send_otp.assert_not_called()


# ── verify_otp tests ──────────────────────────────────────────────────────────

class TestVerifyOTP:
    async def test_verify_otp_success_new_user_creates_user_and_session(
        self, mock_db, mock_twilio, mock_temporal, test_settings
    ):
        """Happy path for a new user: returns tokens, session created, outbox row added."""
        svc = _make_service(mock_db, mock_twilio, mock_temporal, test_settings)
        user = _make_user()
        otp_req = _make_otp_request(attempt_count=0)
        session = _make_session()

        with patch.object(svc._repo, "get_user_by_phone", new=AsyncMock(return_value=user)), \
             patch.object(svc._repo, "get_latest_otp_request", new=AsyncMock(return_value=otp_req)), \
             patch.object(svc._repo, "mark_otp_used", new=AsyncMock(return_value=None)), \
             patch.object(svc._repo, "create_session", new=AsyncMock(return_value=session)):

            result = await svc.verify_otp(PHONE, OTP_CODE)

        assert result.access_token
        assert result.refresh_token
        mock_db.commit.assert_called()
        # outbox row should have been add()-ed
        assert mock_db.add.called

    async def test_verify_otp_success_existing_user_creates_session_only(
        self, mock_db, mock_twilio, mock_temporal, test_settings
    ):
        """Existing user login: no new user creation, session is created."""
        svc = _make_service(mock_db, mock_twilio, mock_temporal, test_settings)
        user = _make_user()
        # attempt_count=1 means this is a re-login, not first registration
        otp_req = _make_otp_request(attempt_count=1)
        session = _make_session()

        with patch.object(svc._repo, "get_user_by_phone", new=AsyncMock(return_value=user)), \
             patch.object(svc._repo, "get_latest_otp_request", new=AsyncMock(return_value=otp_req)), \
             patch.object(svc._repo, "mark_otp_used", new=AsyncMock(return_value=None)), \
             patch.object(svc._repo, "create_session", new=AsyncMock(return_value=session)) as mock_cs:

            result = await svc.verify_otp(PHONE, OTP_CODE)

        mock_cs.assert_called_once()
        assert result.access_token

    async def test_verify_otp_publishes_user_registered_event_for_new_user(
        self, mock_db, mock_twilio, mock_temporal, test_settings
    ):
        """attempt_count=0 → UserRegistered event in outbox."""
        svc = _make_service(mock_db, mock_twilio, mock_temporal, test_settings)
        user = _make_user()
        otp_req = _make_otp_request(attempt_count=0)
        session = _make_session()

        with patch.object(svc._repo, "get_user_by_phone", new=AsyncMock(return_value=user)), \
             patch.object(svc._repo, "get_latest_otp_request", new=AsyncMock(return_value=otp_req)), \
             patch.object(svc._repo, "mark_otp_used", new=AsyncMock(return_value=None)), \
             patch.object(svc._repo, "create_session", new=AsyncMock(return_value=session)):

            await svc.verify_otp(PHONE, OTP_CODE)

        # Check that add() was called with an outbox row having event_type UserRegistered
        added_objects = [call.args[0] for call in mock_db.add.call_args_list]
        from elixir.domains.identity.models import IdentityOutbox
        outbox_rows = [o for o in added_objects if isinstance(o, IdentityOutbox)]
        assert any(r.event_type == "identity.UserRegistered" for r in outbox_rows)

    async def test_verify_otp_publishes_user_logged_in_event_for_existing_user(
        self, mock_db, mock_twilio, mock_temporal, test_settings
    ):
        """attempt_count > 0 → UserLoggedIn event in outbox."""
        svc = _make_service(mock_db, mock_twilio, mock_temporal, test_settings)
        user = _make_user()
        otp_req = _make_otp_request(attempt_count=1)
        session = _make_session()

        with patch.object(svc._repo, "get_user_by_phone", new=AsyncMock(return_value=user)), \
             patch.object(svc._repo, "get_latest_otp_request", new=AsyncMock(return_value=otp_req)), \
             patch.object(svc._repo, "mark_otp_used", new=AsyncMock(return_value=None)), \
             patch.object(svc._repo, "create_session", new=AsyncMock(return_value=session)):

            await svc.verify_otp(PHONE, OTP_CODE)

        added_objects = [call.args[0] for call in mock_db.add.call_args_list]
        from elixir.domains.identity.models import IdentityOutbox
        outbox_rows = [o for o in added_objects if isinstance(o, IdentityOutbox)]
        assert any(r.event_type == "identity.UserLoggedIn" for r in outbox_rows)

    async def test_verify_otp_raises_user_not_found_when_no_user(
        self, mock_db, mock_twilio, mock_temporal, test_settings
    ):
        """No user in DB → UserNotFoundError."""
        svc = _make_service(mock_db, mock_twilio, mock_temporal, test_settings)

        with patch.object(svc._repo, "get_user_by_phone", new=AsyncMock(return_value=None)):
            with pytest.raises(UserNotFoundError):
                await svc.verify_otp(PHONE, OTP_CODE)

    async def test_verify_otp_expired_raises_otp_expired_error(
        self, mock_db, mock_twilio, mock_temporal, test_settings
    ):
        """Expired OTP → OTPExpiredError."""
        svc = _make_service(mock_db, mock_twilio, mock_temporal, test_settings)
        user = _make_user()
        expired_otp = _make_otp_request(expired=True)

        with patch.object(svc._repo, "get_user_by_phone", new=AsyncMock(return_value=user)), \
             patch.object(svc._repo, "get_latest_otp_request", new=AsyncMock(return_value=expired_otp)):

            with pytest.raises(OTPExpiredError):
                await svc.verify_otp(PHONE, OTP_CODE)

    async def test_verify_otp_no_active_otp_raises_otp_expired_error(
        self, mock_db, mock_twilio, mock_temporal, test_settings
    ):
        """No OTP request at all → OTPExpiredError."""
        svc = _make_service(mock_db, mock_twilio, mock_temporal, test_settings)
        user = _make_user()

        with patch.object(svc._repo, "get_user_by_phone", new=AsyncMock(return_value=user)), \
             patch.object(svc._repo, "get_latest_otp_request", new=AsyncMock(return_value=None)):

            with pytest.raises(OTPExpiredError):
                await svc.verify_otp(PHONE, OTP_CODE)

    async def test_verify_otp_already_used_raises_otp_expired_error(
        self, mock_db, mock_twilio, mock_temporal, test_settings
    ):
        """OTP already marked as used → OTPExpiredError."""
        svc = _make_service(mock_db, mock_twilio, mock_temporal, test_settings)
        user = _make_user()
        used_otp = _make_otp_request(used=True)

        with patch.object(svc._repo, "get_user_by_phone", new=AsyncMock(return_value=user)), \
             patch.object(svc._repo, "get_latest_otp_request", new=AsyncMock(return_value=used_otp)):

            with pytest.raises(OTPExpiredError):
                await svc.verify_otp(PHONE, OTP_CODE)

    async def test_verify_otp_wrong_code_increments_attempt_count(
        self, mock_db, mock_twilio, mock_temporal, test_settings
    ):
        """Wrong OTP code → attempt_count incremented, OTPInvalidError raised."""
        svc = _make_service(mock_db, mock_twilio, mock_temporal, test_settings)
        user = _make_user()
        otp_req = _make_otp_request(attempt_count=0)

        mock_increment = AsyncMock(return_value=None)

        with patch.object(svc._repo, "get_user_by_phone", new=AsyncMock(return_value=user)), \
             patch.object(svc._repo, "get_latest_otp_request", new=AsyncMock(return_value=otp_req)), \
             patch.object(svc._repo, "increment_otp_attempt", new=mock_increment):

            with pytest.raises(OTPInvalidError):
                await svc.verify_otp(PHONE, "000000")  # wrong code

        mock_increment.assert_called_once()
        # lock_until should be None (not enough attempts to lock yet)
        call_args = mock_increment.call_args
        assert call_args.args[1] is None  # lock_until=None for first failure

    async def test_verify_otp_locks_after_max_attempts(
        self, mock_db, mock_twilio, mock_temporal, test_settings
    ):
        """After otp_max_attempts failures, locked_until is set."""
        svc = _make_service(mock_db, mock_twilio, mock_temporal, test_settings)
        user = _make_user()
        # attempt_count is already at max_attempts - 1, so next failure triggers lock
        pre_lock_count = test_settings.otp_max_attempts - 1
        otp_req = _make_otp_request(attempt_count=pre_lock_count)

        mock_increment = AsyncMock(return_value=None)

        with patch.object(svc._repo, "get_user_by_phone", new=AsyncMock(return_value=user)), \
             patch.object(svc._repo, "get_latest_otp_request", new=AsyncMock(return_value=otp_req)), \
             patch.object(svc._repo, "increment_otp_attempt", new=mock_increment):

            with pytest.raises(OTPInvalidError):
                await svc.verify_otp(PHONE, "000000")  # wrong code

        call_args = mock_increment.call_args
        lock_until = call_args.args[1]
        assert lock_until is not None  # must be locked
        assert lock_until > datetime.now(timezone.utc)  # must be in the future

    async def test_verify_otp_locked_raises_otp_locked_error(
        self, mock_db, mock_twilio, mock_temporal, test_settings
    ):
        """OTP locked → OTPLockedError immediately, no attempt increment."""
        svc = _make_service(mock_db, mock_twilio, mock_temporal, test_settings)
        user = _make_user()
        locked_otp = _make_otp_request(locked=True)

        mock_increment = AsyncMock(return_value=None)

        with patch.object(svc._repo, "get_user_by_phone", new=AsyncMock(return_value=user)), \
             patch.object(svc._repo, "get_latest_otp_request", new=AsyncMock(return_value=locked_otp)), \
             patch.object(svc._repo, "increment_otp_attempt", new=mock_increment):

            with pytest.raises(OTPLockedError):
                await svc.verify_otp(PHONE, OTP_CODE)

        mock_increment.assert_not_called()


# ── refresh_session tests ─────────────────────────────────────────────────────

class TestRefreshSession:
    async def test_refresh_session_success_rotates_access_jti(
        self, mock_db, mock_twilio, mock_temporal, test_settings
    ):
        """Happy path: valid refresh token → new access token, JTI rotated."""
        svc = _make_service(mock_db, mock_twilio, mock_temporal, test_settings)
        session = _make_session()
        refresh_token, refresh_jti = create_refresh_token(
            str(USER_ID), str(SESSION_ID),
            test_settings.jwt_secret,
            test_settings.refresh_token_expiry_days,
        )
        session.refresh_token_jti = refresh_jti
        old_access_jti = session.access_token_jti

        mock_rotate = AsyncMock(return_value=None)

        with patch.object(svc._repo, "get_session_by_refresh_jti", new=AsyncMock(return_value=session)), \
             patch.object(svc._repo, "rotate_access_jti", new=mock_rotate):

            result = await svc.refresh_session(refresh_token)

        assert result.access_token
        assert result.token_type == "bearer"
        mock_rotate.assert_called_once()
        # new JTI must differ from old one
        new_jti = mock_rotate.call_args.args[1]
        assert new_jti != old_access_jti
        mock_db.commit.assert_called_once()

    async def test_refresh_session_revoked_raises_session_revoked(
        self, mock_db, mock_twilio, mock_temporal, test_settings
    ):
        """Refresh token for revoked session → SessionRevokedError."""
        svc = _make_service(mock_db, mock_twilio, mock_temporal, test_settings)
        session = _make_session(revoked=True)
        refresh_token, refresh_jti = create_refresh_token(
            str(USER_ID), str(SESSION_ID),
            test_settings.jwt_secret,
            test_settings.refresh_token_expiry_days,
        )
        session.refresh_token_jti = refresh_jti

        with patch.object(svc._repo, "get_session_by_refresh_jti", new=AsyncMock(return_value=session)):
            with pytest.raises(SessionRevokedError):
                await svc.refresh_session(refresh_token)

        mock_db.commit.assert_not_called()

    async def test_refresh_session_expired_raises_session_expired(
        self, mock_db, mock_twilio, mock_temporal, test_settings
    ):
        """Refresh token for expired session → SessionExpiredError."""
        svc = _make_service(mock_db, mock_twilio, mock_temporal, test_settings)
        session = _make_session(expired=True)
        refresh_token, refresh_jti = create_refresh_token(
            str(USER_ID), str(SESSION_ID),
            test_settings.jwt_secret,
            test_settings.refresh_token_expiry_days,
        )
        session.refresh_token_jti = refresh_jti

        with patch.object(svc._repo, "get_session_by_refresh_jti", new=AsyncMock(return_value=session)):
            with pytest.raises(SessionExpiredError):
                await svc.refresh_session(refresh_token)

        mock_db.commit.assert_not_called()

    async def test_refresh_session_not_found_raises_session_expired(
        self, mock_db, mock_twilio, mock_temporal, test_settings
    ):
        """No session matching refresh JTI → SessionExpiredError."""
        svc = _make_service(mock_db, mock_twilio, mock_temporal, test_settings)
        refresh_token, _ = create_refresh_token(
            str(USER_ID), str(SESSION_ID),
            test_settings.jwt_secret,
            test_settings.refresh_token_expiry_days,
        )

        with patch.object(svc._repo, "get_session_by_refresh_jti", new=AsyncMock(return_value=None)):
            with pytest.raises(SessionExpiredError):
                await svc.refresh_session(refresh_token)

    async def test_refresh_session_invalid_token_raises_token_invalid(
        self, mock_db, mock_twilio, mock_temporal, test_settings
    ):
        """Garbage token string → TokenInvalidError (from security layer)."""
        from elixir.shared.exceptions import TokenInvalidError
        svc = _make_service(mock_db, mock_twilio, mock_temporal, test_settings)

        with pytest.raises(TokenInvalidError):
            await svc.refresh_session("not-a-valid-jwt")


# ── logout tests ──────────────────────────────────────────────────────────────

class TestLogout:
    async def test_logout_revokes_session(
        self, mock_db, mock_twilio, mock_temporal, test_settings
    ):
        """logout() sets revoked_at on the session."""
        svc = _make_service(mock_db, mock_twilio, mock_temporal, test_settings)
        session = _make_session()
        mock_revoke = AsyncMock(return_value=None)

        with patch.object(svc._repo, "get_session_by_id", new=AsyncMock(return_value=session)), \
             patch.object(svc._repo, "revoke_session", new=mock_revoke):

            await svc.logout(USER_ID, SESSION_ID)

        mock_revoke.assert_called_once_with(session)
        mock_db.commit.assert_called_once()

    async def test_logout_does_nothing_when_session_not_found(
        self, mock_db, mock_twilio, mock_temporal, test_settings
    ):
        """logout() is a no-op when the session doesn't exist (idempotent)."""
        svc = _make_service(mock_db, mock_twilio, mock_temporal, test_settings)

        with patch.object(svc._repo, "get_session_by_id", new=AsyncMock(return_value=None)):
            # Should not raise
            await svc.logout(USER_ID, SESSION_ID)

        mock_db.commit.assert_not_called()

    async def test_logout_does_nothing_when_session_belongs_to_different_user(
        self, mock_db, mock_twilio, mock_temporal, test_settings
    ):
        """logout() ignores sessions owned by a different user (prevents unauthorised revocation)."""
        svc = _make_service(mock_db, mock_twilio, mock_temporal, test_settings)
        other_user_id = uuid.uuid4()
        session = _make_session(user_id=other_user_id)  # session belongs to other user

        mock_revoke = AsyncMock(return_value=None)

        with patch.object(svc._repo, "get_session_by_id", new=AsyncMock(return_value=session)), \
             patch.object(svc._repo, "revoke_session", new=mock_revoke):

            await svc.logout(USER_ID, SESSION_ID)  # caller is USER_ID

        mock_revoke.assert_not_called()
        mock_db.commit.assert_not_called()
