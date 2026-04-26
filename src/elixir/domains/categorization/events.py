import logging
from typing import ClassVar

from sqlalchemy.ext.asyncio import AsyncSession

from elixir.shared.events import EventPayload

logger = logging.getLogger(__name__)


# ── Event dataclasses ─────────────────────────────────────────────────────────

class CategoryCreated:
    event_type: ClassVar[str] = "categorization.CategoryCreated"

    def __init__(
        self,
        category_id: str,
        user_id: str,
        name: str,
        kind: str,
    ) -> None:
        self.category_id = category_id
        self.user_id = user_id
        self.name = name
        self.kind = kind

    def to_payload(self) -> dict:
        return {
            "category_id": self.category_id,
            "user_id": self.user_id,
            "name": self.name,
            "kind": self.kind,
        }


# ── Event handlers (subscribed via bootstrap) ─────────────────────────────────

async def handle_category_created(payload: EventPayload, session: AsyncSession) -> None:
    """Placeholder for downstream reactions to a new category being created."""
    logger.info(
        "Category created: %s (kind=%s) for user %s",
        payload.get("category_id"),
        payload.get("kind"),
        payload.get("user_id"),
    )
