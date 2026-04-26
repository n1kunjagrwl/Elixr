import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, status

from elixir.domains.peers.schemas import (
    PeerBalanceCreate,
    PeerBalanceResponse,
    PeerBalanceUpdate,
    PeerContactCreate,
    PeerContactResponse,
    PeerContactUpdate,
    PeerSettlementCreate,
    PeerSettlementResponse,
)
from elixir.domains.peers.services import PeersService
from elixir.runtime.dependencies import RequestCtx, get_db_session

router = APIRouter()


# ── Service factory ───────────────────────────────────────────────────────────

def get_peers_service(
    db=Depends(get_db_session),
) -> PeersService:
    return PeersService(db=db)


PeersSvc = Annotated[PeersService, Depends(get_peers_service)]


# ── Contacts ──────────────────────────────────────────────────────────────────

@router.get("/contacts", response_model=list[PeerContactResponse])
async def get_contacts(ctx: RequestCtx, svc: PeersSvc):
    """List all peer contacts for the authenticated user."""
    return await svc.list_contacts(ctx.user_id)


@router.post(
    "/contacts",
    response_model=PeerContactResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_contact(
    body: PeerContactCreate,
    ctx: RequestCtx,
    svc: PeersSvc,
):
    """Add a new peer contact for the authenticated user."""
    return await svc.add_contact(ctx.user_id, body)


@router.patch("/contacts/{contact_id}", response_model=PeerContactResponse)
async def edit_contact(
    contact_id: uuid.UUID,
    body: PeerContactUpdate,
    ctx: RequestCtx,
    svc: PeersSvc,
):
    """Partially update a peer contact owned by the authenticated user."""
    return await svc.edit_contact(ctx.user_id, contact_id, body)


@router.delete("/contacts/{contact_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_contact(
    contact_id: uuid.UUID,
    ctx: RequestCtx,
    svc: PeersSvc,
):
    """Delete a peer contact (only if no open/partial balances)."""
    await svc.delete_contact(ctx.user_id, contact_id)


# ── Balances ──────────────────────────────────────────────────────────────────

@router.get("/balances", response_model=list[PeerBalanceResponse])
async def get_balances(
    ctx: RequestCtx,
    svc: PeersSvc,
    status: Annotated[
        Literal["open", "partial", "settled"] | None, Query()
    ] = None,
):
    """List peer balances for the authenticated user. Optional ?status filter."""
    return await svc.list_balances(ctx.user_id, status=status)


@router.post(
    "/balances",
    response_model=PeerBalanceResponse,
    status_code=status.HTTP_201_CREATED,
)
async def log_balance(
    body: PeerBalanceCreate,
    ctx: RequestCtx,
    svc: PeersSvc,
):
    """Log a new peer balance for the authenticated user."""
    return await svc.log_balance(ctx.user_id, body)


@router.patch("/balances/{balance_id}", response_model=PeerBalanceResponse)
async def edit_balance(
    balance_id: uuid.UUID,
    body: PeerBalanceUpdate,
    ctx: RequestCtx,
    svc: PeersSvc,
):
    """Update description/notes of a peer balance (amount cannot be changed)."""
    return await svc.edit_balance(ctx.user_id, balance_id, body)


# ── Settlements ───────────────────────────────────────────────────────────────

@router.get(
    "/balances/{balance_id}/settlements",
    response_model=list[PeerSettlementResponse],
)
async def get_settlements(
    balance_id: uuid.UUID,
    ctx: RequestCtx,
    svc: PeersSvc,
):
    """List all settlements for a given balance."""
    return await svc.list_settlements(ctx.user_id, balance_id)


@router.post(
    "/balances/{balance_id}/settlements",
    response_model=PeerSettlementResponse,
    status_code=status.HTTP_201_CREATED,
)
async def record_settlement(
    balance_id: uuid.UUID,
    body: PeerSettlementCreate,
    ctx: RequestCtx,
    svc: PeersSvc,
):
    """Record a new settlement for a peer balance."""
    return await svc.record_settlement(ctx.user_id, balance_id, body)
