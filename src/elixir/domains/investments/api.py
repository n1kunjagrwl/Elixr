from __future__ import annotations

import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, status

from elixir.domains.investments.schemas import (
    FDDetailsCreate,
    FDDetailsResponse,
    HoldingCreate,
    HoldingResponse,
    HoldingUpdate,
    InstrumentCreate,
    InstrumentResponse,
    SIPConfirmRequest,
    SIPCreate,
    SIPResponse,
    SIPUpdate,
)
from elixir.domains.investments.services import InvestmentsService
from elixir.runtime.dependencies import RequestCtx, get_db_session

router = APIRouter()


# ── Service factory ────────────────────────────────────────────────────────────


def get_investments_service(
    db=Depends(get_db_session),
) -> InvestmentsService:
    return InvestmentsService(db=db)


InvestmentsSvc = Annotated[InvestmentsService, Depends(get_investments_service)]


# ── Instruments ────────────────────────────────────────────────────────────────


@router.get("/instruments", response_model=list[InstrumentResponse])
async def get_instruments(
    ctx: RequestCtx,
    svc: InvestmentsSvc,
    q: str | None = None,
    type_filter: str | None = None,
):
    """Search instruments by name with optional type filter."""
    return await svc.search_instruments(q=q, type_filter=type_filter)


@router.post(
    "/instruments",
    response_model=InstrumentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_instrument(
    body: InstrumentCreate,
    ctx: RequestCtx,
    svc: InvestmentsSvc,
):
    """Create a new instrument in the shared master registry."""
    return await svc.create_instrument(body)


# ── Holdings ───────────────────────────────────────────────────────────────────


@router.get("/holdings", response_model=list[HoldingResponse])
async def get_holdings(ctx: RequestCtx, svc: InvestmentsSvc):
    """List all holdings for the authenticated user."""
    return await svc.list_holdings(ctx.user_id)


@router.post(
    "/holdings",
    response_model=HoldingResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_holding(
    body: HoldingCreate,
    ctx: RequestCtx,
    svc: InvestmentsSvc,
):
    """Add a new holding for the authenticated user."""
    return await svc.add_holding(ctx.user_id, body)


@router.patch("/holdings/{holding_id}", response_model=HoldingResponse)
async def edit_holding(
    holding_id: uuid.UUID,
    body: HoldingUpdate,
    ctx: RequestCtx,
    svc: InvestmentsSvc,
):
    """Partially update a holding owned by the authenticated user."""
    return await svc.edit_holding(ctx.user_id, holding_id, body)


@router.delete("/holdings/{holding_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_holding(
    holding_id: uuid.UUID,
    ctx: RequestCtx,
    svc: InvestmentsSvc,
):
    """Remove a holding owned by the authenticated user."""
    await svc.remove_holding(ctx.user_id, holding_id)


# ── FD Details ─────────────────────────────────────────────────────────────────


@router.post(
    "/holdings/{holding_id}/fd",
    response_model=FDDetailsResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_fd_details(
    holding_id: uuid.UUID,
    body: FDDetailsCreate,
    ctx: RequestCtx,
    svc: InvestmentsSvc,
):
    """Add Fixed Deposit details to a holding of type 'fd'."""
    return await svc.add_fd_details(ctx.user_id, holding_id, body)


# ── Portfolio History ──────────────────────────────────────────────────────────


@router.get("/history")
async def get_portfolio_history(
    ctx: RequestCtx,
    svc: InvestmentsSvc,
    from_date: date | None = None,
    to_date: date | None = None,
):
    """Get daily portfolio valuation history for the authenticated user."""
    return await svc.get_portfolio_history(
        user_id=ctx.user_id,
        from_date=from_date,
        to_date=to_date,
    )


# ── SIP Registrations ──────────────────────────────────────────────────────────


@router.get("/sip", response_model=list[SIPResponse])
async def get_sips(ctx: RequestCtx, svc: InvestmentsSvc):
    """List all SIP registrations for the authenticated user."""
    return await svc.list_sips(ctx.user_id)


@router.post(
    "/sip",
    response_model=SIPResponse,
    status_code=status.HTTP_201_CREATED,
)
async def register_sip(
    body: SIPCreate,
    ctx: RequestCtx,
    svc: InvestmentsSvc,
):
    """Register a new SIP for the authenticated user."""
    return await svc.register_sip(ctx.user_id, body)


@router.patch("/sip/{sip_id}", response_model=SIPResponse)
async def edit_sip(
    sip_id: uuid.UUID,
    body: SIPUpdate,
    ctx: RequestCtx,
    svc: InvestmentsSvc,
):
    """Partially update a SIP registration."""
    return await svc.edit_sip(ctx.user_id, sip_id, body)


@router.delete("/sip/{sip_id}", status_code=status.HTTP_204_NO_CONTENT)
async def deactivate_sip(
    sip_id: uuid.UUID,
    ctx: RequestCtx,
    svc: InvestmentsSvc,
):
    """Deactivate a SIP registration (soft delete)."""
    await svc.deactivate_sip(ctx.user_id, sip_id)


@router.post("/sip/{sip_id}/confirm")
async def confirm_sip(
    sip_id: uuid.UUID,
    body: SIPConfirmRequest,
    ctx: RequestCtx,
    svc: InvestmentsSvc,
):
    """Confirm a detected SIP match, linking the transaction to the SIP."""
    await svc.confirm_sip_link(ctx.user_id, sip_id, body.transaction_id)
    return {"status": "confirmed"}
