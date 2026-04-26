import uuid
from datetime import date, datetime, timezone

from sqlalchemy import and_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from elixir.domains.notifications.models import Notification


class NotificationsRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def create_notification(
        self,
        user_id: uuid.UUID,
        type_: str,
        title: str,
        body: str,
        route: str,
        primary_entity_id: uuid.UUID | None = None,
        secondary_entity_id: uuid.UUID | None = None,
        period_start: date | None = None,
    ) -> Notification:
        notification = Notification(
            user_id=user_id,
            type=type_,
            title=title,
            body=body,
            route=route,
            primary_entity_id=primary_entity_id,
            secondary_entity_id=secondary_entity_id,
            period_start=period_start,
        )
        self._db.add(notification)
        await self._db.flush()
        return notification

    async def notification_exists(
        self,
        user_id: uuid.UUID,
        type_: str,
        primary_entity_id: uuid.UUID | None = None,
        secondary_entity_id: uuid.UUID | None = None,
        period_start: date | None = None,
    ) -> bool:
        conditions = [
            Notification.user_id == user_id,
            Notification.type == type_,
        ]
        if primary_entity_id is not None:
            conditions.append(Notification.primary_entity_id == primary_entity_id)
        if secondary_entity_id is not None:
            conditions.append(Notification.secondary_entity_id == secondary_entity_id)
        if period_start is not None:
            conditions.append(Notification.period_start == period_start)

        result = await self._db.execute(
            select(Notification.id).where(and_(*conditions)).limit(1)
        )
        return result.scalar_one_or_none() is not None

    async def list_notifications(
        self,
        user_id: uuid.UUID,
        unread_only: bool = False,
        page: int = 1,
        page_size: int = 20,
    ) -> list[Notification]:
        query = select(Notification).where(Notification.user_id == user_id)
        if unread_only:
            query = query.where(Notification.read_at.is_(None))
        query = query.order_by(Notification.created_at.desc())
        offset = (page - 1) * page_size
        query = query.offset(offset).limit(page_size)
        result = await self._db.execute(query)
        return list(result.scalars().all())

    async def get_notification(
        self, user_id: uuid.UUID, notification_id: uuid.UUID
    ) -> Notification | None:
        result = await self._db.execute(
            select(Notification).where(
                Notification.id == notification_id,
                Notification.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    async def mark_read(self, notification: Notification) -> None:
        if notification.read_at is None:
            notification.read_at = datetime.now(timezone.utc)

    async def mark_all_read(self, user_id: uuid.UUID) -> int:
        result = await self._db.execute(
            update(Notification)
            .where(
                Notification.user_id == user_id,
                Notification.read_at.is_(None),
            )
            .values(read_at=datetime.now(timezone.utc))
        )
        return result.rowcount
