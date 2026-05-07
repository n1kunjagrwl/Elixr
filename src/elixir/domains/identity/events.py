from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from elixir.shared.events import EventPayload


async def handle_user_registered(payload: EventPayload, session: AsyncSession) -> None:
    """
    Placeholder for downstream reactions to new user registration
    (e.g., seed default categories, send welcome notification).
    Idempotent: checks before acting.
    """
    logger.info("New user registered: {}", payload.get("user_id"))


async def handle_user_logged_in(payload: EventPayload, session: AsyncSession) -> None:
    logger.debug("User logged in: {}", payload.get("user_id"))
