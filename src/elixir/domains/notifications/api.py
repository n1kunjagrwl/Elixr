import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status

from elixir.domains.notifications.schemas import NotificationResponse
from elixir.domains.notifications.services import NotificationsService
from elixir.runtime.dependencies import RequestCtx, get_db_session

router = APIRouter()


# ── Service factory ────────────────────────────────────────────────────────────

def get_notifications_service(
    db=Depends(get_db_session),
) -> NotificationsService:
    return NotificationsService(db=db)


NotificationsSvc = Annotated[NotificationsService, Depends(get_notifications_service)]


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.get("", response_model=list[NotificationResponse])
async def list_notifications(
    ctx: RequestCtx,
    svc: NotificationsSvc,
    unread: bool = False,
    page: int = 1,
    page_size: int = 20,
):
    """List notifications for the authenticated user (most recent first)."""
    return await svc.list_notifications(
        ctx.user_id, unread_only=unread, page=page, page_size=page_size
    )


@router.patch("/read-all")
async def mark_all_read(ctx: RequestCtx, svc: NotificationsSvc):
    """Mark all unread notifications as read. Returns count of rows updated."""
    return await svc.mark_all_read(ctx.user_id)


@router.patch("/{notification_id}/read")
async def mark_read(
    notification_id: uuid.UUID,
    ctx: RequestCtx,
    svc: NotificationsSvc,
):
    """Mark a single notification as read (no-op if already read)."""
    await svc.mark_read(ctx.user_id, notification_id)
    return {"ok": True}
