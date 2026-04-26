import asyncio
import logging
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from elixir.shared.events import EventBus

logger = logging.getLogger(__name__)


class OutboxPoller:
    """
    Background task that polls each domain's outbox table for pending events
    and dispatches them to the EventBus. Provides at-least-once delivery —
    handlers MUST be idempotent.
    """

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        event_bus: EventBus,
        poll_interval_seconds: int = 2,
    ) -> None:
        self._session_factory = session_factory
        self._event_bus = event_bus
        self._interval = poll_interval_seconds

    async def run(self) -> None:
        logger.info("OutboxPoller started (interval=%ds)", self._interval)
        while True:
            try:
                await self._poll_once()
            except asyncio.CancelledError:
                logger.info("OutboxPoller shutting down")
                raise
            except Exception:
                logger.exception("OutboxPoller error — continuing")
            await asyncio.sleep(self._interval)

    async def _poll_once(self) -> None:
        for table in self._event_bus.outbox_tables:
            await self._poll_table(table)

    async def _poll_table(self, table: str) -> None:
        async with self._session_factory() as session:
            rows = await self._fetch_pending(session, table)
            for row in rows:
                await self._dispatch_row(session, table, row)

    async def _fetch_pending(self, session: AsyncSession, table: str) -> list[Any]:
        result = await session.execute(
            text(
                f"SELECT id, event_type, payload FROM {table} "
                "WHERE status = 'pending' ORDER BY created_at LIMIT 100"
            )
        )
        return list(result.fetchall())

    async def _dispatch_row(self, session: AsyncSession, table: str, row) -> None:
        try:
            await self._event_bus.dispatch(row.event_type, row.payload, session)
            await session.execute(
                text(
                    f"UPDATE {table} SET status = 'processed', processed_at = now() WHERE id = :id"
                ),
                {"id": row.id},
            )
            await session.commit()
        except Exception:
            await session.rollback()
            logger.exception(
                "Failed to dispatch outbox row",
                extra={"table": table, "row_id": str(row.id), "event_type": row.event_type},
            )
