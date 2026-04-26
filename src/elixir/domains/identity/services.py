from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Protocol
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from elixir.domains.identity.models import IdentityOutbox
from elixir.domains.identity.repositories import IdentityRepository
from elixir.domains.identity.schemas import OTPRequestedResponse, RefreshResponse, VerifyOTPResponse
from elixir.shared.config import Settings
from elixir.shared.exceptions import (
    OTPExpiredError,
    OTPInvalidError,
    OTPLockedError,
    RateLimitError,
    SessionExpiredError,
    SessionRevokedError,
    TokenExpiredError,
    TokenInvalidError,
    UserNotFoundError,
)
from elixir.shared.security import generate_otp, hash_otp, verify_otp_hash

# Identity domain intentionally imports from platform.security because it IS
# the auth infrastructure owner. This is the only domain with this exception
# to the platform import rule.
from elixir.platform.security import (
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
    TokenExpiredError as PlatformTokenExpiredError,
    TokenInvalidError as PlatformTokenInvalidError,
)


# ── Service Protocol (Liskov / Dependency Inversion) ─────────────────

class IdentityServiceProtocol(Protocol):
    async def request_otp(self, phone: str) -> OTPRequestedResponse: ...
    async def verify_otp(self, phone: str, otp_code: str) -> "_OTPVerificationResult": ...
    async def refresh_session(self, refresh_token: str) -> RefreshResponse: ...
    async def logout(self, user_id: UUID, session_id: UUID) -> None: ...


@dataclass
class _OTPVerificationResult:
    """Internal result — split into access_token and refresh_token for the API layer to handle cookies."""
    access_token: str
    refresh_token: str


# ── Concrete Implementation ───────────────────────────────────────────

class IdentityService:
    def __init__(
        self,
        db: AsyncSession,
        twilio,
        temporal_client,
        settings: Settings,
    ) -> None:
        self._db = db
        self._repo = IdentityRepository(db)
        self._twilio = twilio
        self._temporal = temporal_client
        self._settings = settings

    async def request_otp(self, phone: str) -> OTPRequestedResponse:
        user, _created = await self._repo.get_or_create_user(phone)

        # Rate limit: max N OTP requests per phone per window
        window_start = datetime.now(timezone.utc) - timedelta(
            minutes=self._settings.otp_rate_limit_window_minutes
        )
        count = await self._repo.count_recent_otp_requests(user.id, since=window_start)
        if count >= self._settings.otp_rate_limit_count:
            raise RateLimitError(
                "Too many OTP requests. Please wait before requesting again.",
                phone=phone,
            )

        # Check active lockout
        latest = await self._repo.get_latest_otp_request(user.id)
        if latest and latest.locked_until and latest.locked_until > datetime.now(timezone.utc):
            raise OTPLockedError(
                "Account temporarily locked due to too many failed attempts.",
                locked_until=latest.locked_until.isoformat(),
            )

        # Generate and hash OTP
        otp_code = generate_otp()
        code_hash = hash_otp(otp_code)
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=self._settings.otp_expiry_seconds)

        otp_req = await self._repo.create_otp_request(user.id, code_hash, expires_at)
        await self._db.commit()

        # Trigger OTP delivery via Temporal (fire-and-forget)
        if self._temporal:
            try:
                from elixir.domains.identity.workflows.otp_delivery import OTPDeliveryWorkflow, OTPWorkflowInput
                await self._temporal.start_workflow(
                    OTPDeliveryWorkflow.run,
                    OTPWorkflowInput(
                        user_id=str(user.id),
                        phone_e164=phone,
                        otp_code=otp_code,
                        otp_request_id=str(otp_req.id),
                    ),
                    id=f"otp-{user.id}-{otp_req.id}",
                    task_queue=self._settings.temporal_task_queue,
                )
            except Exception:
                import logging
                logging.getLogger(__name__).warning("Temporal unavailable — falling back to direct SMS", exc_info=True)
                await self._twilio.send_otp(phone, otp_code)

        return OTPRequestedResponse(expires_in=self._settings.otp_expiry_seconds)

    async def verify_otp(self, phone: str, otp_code: str) -> _OTPVerificationResult:
        user = await self._repo.get_user_by_phone(phone)
        if not user:
            raise UserNotFoundError(f"No user found for phone {phone}")

        otp_req = await self._repo.get_latest_otp_request(user.id)
        if not otp_req or otp_req.used_at is not None:
            raise OTPExpiredError("No active OTP found. Please request a new one.")

        now = datetime.now(timezone.utc)

        if otp_req.expires_at < now:
            raise OTPExpiredError("OTP has expired. Please request a new one.")

        if otp_req.locked_until and otp_req.locked_until > now:
            raise OTPLockedError("Too many failed attempts. Please wait before trying again.")

        if not verify_otp_hash(otp_code, otp_req.code_hash):
            lock_until = None
            if otp_req.attempt_count + 1 >= self._settings.otp_max_attempts:
                lock_until = now + timedelta(minutes=self._settings.otp_lockout_minutes)
            await self._repo.increment_otp_attempt(otp_req, lock_until)
            await self._db.commit()
            raise OTPInvalidError("Invalid OTP.")

        # Mark OTP as used
        await self._repo.mark_otp_used(otp_req)

        # Create session
        session_id_placeholder = "pending"  # will be replaced after session is created
        session = await self._repo.create_session(
            user_id=user.id,
            access_jti="pending",
            refresh_jti="pending",
            expires_at=now + timedelta(days=self._settings.refresh_token_expiry_days),
        )
        await self._db.flush()

        # Generate tokens (session.id is now available)
        access_token, access_jti = create_access_token(
            str(user.id), str(session.id),
            self._settings.jwt_secret,
            self._settings.access_token_expiry_minutes,
        )
        refresh_token, refresh_jti = create_refresh_token(
            str(user.id), str(session.id),
            self._settings.jwt_secret,
            self._settings.refresh_token_expiry_days,
        )
        session.access_token_jti = access_jti
        session.refresh_token_jti = refresh_jti

        # Publish event via outbox
        event_type = "identity.UserRegistered" if otp_req.attempt_count == 0 else "identity.UserLoggedIn"
        self._db.add(IdentityOutbox(
            event_type=event_type,
            payload={"user_id": str(user.id), "phone_e164": phone},
        ))

        await self._db.commit()
        return _OTPVerificationResult(access_token=access_token, refresh_token=refresh_token)

    async def refresh_session(self, refresh_token: str) -> RefreshResponse:
        try:
            claims = decode_refresh_token(refresh_token, self._settings.jwt_secret)
        except PlatformTokenExpiredError:
            raise TokenExpiredError("Refresh token has expired")
        except PlatformTokenInvalidError as e:
            raise TokenInvalidError(str(e))
        session = await self._repo.get_session_by_refresh_jti(claims["jti"])

        if not session:
            raise SessionExpiredError("Session not found.")

        now = datetime.now(timezone.utc)
        if session.revoked_at is not None:
            raise SessionRevokedError("Session has been revoked.")
        if session.expires_at < now:
            raise SessionExpiredError("Session has expired.")

        new_access_token, new_jti = create_access_token(
            str(session.user_id), str(session.id),
            self._settings.jwt_secret,
            self._settings.access_token_expiry_minutes,
        )
        await self._repo.rotate_access_jti(session, new_jti)
        await self._db.commit()

        return RefreshResponse(access_token=new_access_token)

    async def logout(self, user_id: UUID, session_id: UUID) -> None:
        session = await self._repo.get_session_by_id(session_id)
        if session and session.user_id == user_id:
            await self._repo.revoke_session(session)
            await self._db.commit()
