from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from elixir.domains.identity.models import OTPRequest, Session, User


class IdentityRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    # ── Users ─────────────────────────────────────────────────────────

    async def get_user_by_phone(self, phone_e164: str) -> User | None:
        result = await self._db.execute(
            select(User).where(User.phone_e164 == phone_e164)
        )
        return result.scalar_one_or_none()

    async def get_user_by_id(self, user_id: UUID) -> User | None:
        result = await self._db.execute(
            select(User).where(User.id == user_id)
        )
        return result.scalar_one_or_none()

    async def create_user(self, phone_e164: str) -> User:
        user = User(phone_e164=phone_e164)
        self._db.add(user)
        await self._db.flush()
        return user

    async def get_or_create_user(self, phone_e164: str) -> tuple[User, bool]:
        """Returns (user, created). created=True if the user was just inserted."""
        user = await self.get_user_by_phone(phone_e164)
        if user:
            return user, False
        user = await self.create_user(phone_e164)
        return user, True

    # ── OTP Requests ──────────────────────────────────────────────────

    async def get_latest_otp_request(self, user_id: UUID) -> OTPRequest | None:
        result = await self._db.execute(
            select(OTPRequest)
            .where(OTPRequest.user_id == user_id)
            .order_by(OTPRequest.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def count_recent_otp_requests(self, user_id: UUID, since: datetime) -> int:
        from sqlalchemy import func
        result = await self._db.execute(
            select(func.count()).where(
                OTPRequest.user_id == user_id,
                OTPRequest.created_at >= since,
            )
        )
        return result.scalar_one()

    async def create_otp_request(
        self, user_id: UUID, code_hash: str, expires_at: datetime
    ) -> OTPRequest:
        otp_req = OTPRequest(user_id=user_id, code_hash=code_hash, expires_at=expires_at)
        self._db.add(otp_req)
        await self._db.flush()
        return otp_req

    async def increment_otp_attempt(self, otp_req: OTPRequest, lock_until: datetime | None) -> None:
        otp_req.attempt_count += 1
        otp_req.locked_until = lock_until

    async def mark_otp_used(self, otp_req: OTPRequest) -> None:
        otp_req.used_at = datetime.now(timezone.utc)

    # ── Sessions ──────────────────────────────────────────────────────

    async def create_session(
        self,
        user_id: UUID,
        access_jti: str,
        refresh_jti: str,
        expires_at: datetime,
    ) -> Session:
        session = Session(
            user_id=user_id,
            access_token_jti=access_jti,
            refresh_token_jti=refresh_jti,
            expires_at=expires_at,
        )
        self._db.add(session)
        await self._db.flush()
        return session

    async def get_session_by_id(self, session_id: UUID) -> Session | None:
        result = await self._db.execute(
            select(Session).where(Session.id == session_id)
        )
        return result.scalar_one_or_none()

    async def get_session_by_id_and_user(self, user_id: UUID, session_id: UUID) -> Session | None:
        """Fetch a session scoped to a specific user — used for revocation checks."""
        result = await self._db.execute(
            select(Session).where(
                Session.id == session_id,
                Session.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_session_by_refresh_jti(self, jti: str) -> Session | None:
        result = await self._db.execute(
            select(Session).where(Session.refresh_token_jti == jti)
        )
        return result.scalar_one_or_none()

    async def revoke_session(self, session: Session) -> None:
        session.revoked_at = datetime.now(timezone.utc)

    async def rotate_access_jti(self, session: Session, new_jti: str) -> None:
        session.access_token_jti = new_jti
