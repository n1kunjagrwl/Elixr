import logging
from collections import defaultdict
from typing import Awaitable, Callable

from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

EventPayload = dict
EventHandler = Callable[[EventPayload, AsyncSession], Awaitable[None]]


class EventBus:
    """
    In-process event bus. Handlers are registered at startup by each domain's
    bootstrap.register_event_handlers(). Dispatch is called by OutboxPoller for
    each pending outbox row.
    """

    def __init__(self) -> None:
        self._handlers: dict[str, list[EventHandler]] = defaultdict(list)
        self._outbox_tables: list[str] = []

    def subscribe(self, event_type: str, handler: EventHandler) -> None:
        self._handlers[event_type].append(handler)

    def register_outbox_table(self, table_name: str) -> None:
        self._outbox_tables.append(table_name)

    async def dispatch(
        self, event_type: str, payload: EventPayload, session: AsyncSession
    ) -> None:
        handlers = self._handlers.get(event_type, [])
        for handler in handlers:
            try:
                await handler(payload, session)
            except Exception:
                logger.exception(
                    "Event handler failed",
                    extra={"event_type": event_type, "handler": handler.__qualname__},
                )
                raise

    @property
    def outbox_tables(self) -> list[str]:
        return list(self._outbox_tables)
