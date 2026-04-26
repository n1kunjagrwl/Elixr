import logging
from typing import ClassVar

from sqlalchemy.ext.asyncio import AsyncSession

from elixir.shared.events import EventPayload

logger = logging.getLogger(__name__)


# ── Event dataclasses ─────────────────────────────────────────────────────────

class AccountLinked:
    event_type: ClassVar[str] = "accounts.AccountLinked"

    def __init__(
        self,
        account_id: str,
        user_id: str,
        account_kind: str,
        nickname: str,
    ) -> None:
        self.account_id = account_id
        self.user_id = user_id
        self.account_kind = account_kind
        self.nickname = nickname

    def to_payload(self) -> dict:
        return {
            "account_id": self.account_id,
            "user_id": self.user_id,
            "account_kind": self.account_kind,
            "nickname": self.nickname,
        }


class AccountRemoved:
    event_type: ClassVar[str] = "accounts.AccountRemoved"

    def __init__(
        self,
        account_id: str,
        user_id: str,
        account_kind: str,
    ) -> None:
        self.account_id = account_id
        self.user_id = user_id
        self.account_kind = account_kind

    def to_payload(self) -> dict:
        return {
            "account_id": self.account_id,
            "user_id": self.user_id,
            "account_kind": self.account_kind,
        }


# ── Event handlers (subscribed via bootstrap) ─────────────────────────────────

async def handle_account_linked(payload: EventPayload, session: AsyncSession) -> None:
    """Placeholder for downstream reactions to a new account being linked."""
    logger.info(
        "Account linked: %s (kind=%s) for user %s",
        payload.get("account_id"),
        payload.get("account_kind"),
        payload.get("user_id"),
    )


async def handle_account_removed(payload: EventPayload, session: AsyncSession) -> None:
    """Placeholder for downstream reactions to an account being deactivated."""
    logger.info(
        "Account removed: %s (kind=%s) for user %s",
        payload.get("account_id"),
        payload.get("account_kind"),
        payload.get("user_id"),
    )
