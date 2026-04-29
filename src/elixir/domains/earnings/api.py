import uuid
from datetime import date as date_type
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from elixir.domains.earnings.schemas import (
    ClassifyTransactionRequest,
    EarningCreate,
    EarningFilters,
    EarningResponse,
    EarningSourceCreate,
    EarningSourceResponse,
    EarningSourceUpdate,
    EarningUpdate,
    EarningType,
)
from elixir.domains.earnings.services import EarningsService
from elixir.runtime.dependencies import RequestCtx, get_db_session

router = APIRouter()


def get_earnings_service(
    db=Depends(get_db_session),
) -> EarningsService:
    return EarningsService(db=db)


EarningsSvc = Annotated[EarningsService, Depends(get_earnings_service)]


@router.get("", response_model=list[EarningResponse])
async def get_earnings(
    ctx: RequestCtx,
    svc: EarningsSvc,
    source_type: EarningType | None = Query(default=None),
    date_from: date_type | None = Query(default=None),
    date_to: date_type | None = Query(default=None),
    source_id: uuid.UUID | None = Query(default=None),
):
    filters = EarningFilters(
        source_type=source_type,
        date_from=date_from,
        date_to=date_to,
        source_id=source_id,
    )
    return await svc.list_earnings(ctx.user_id, filters)


@router.post("", response_model=EarningResponse, status_code=status.HTTP_201_CREATED)
async def add_earning(
    body: EarningCreate,
    ctx: RequestCtx,
    svc: EarningsSvc,
):
    return await svc.add_manual_earning(ctx.user_id, body)


@router.patch("/{earning_id}", response_model=EarningResponse)
async def edit_earning(
    earning_id: uuid.UUID,
    body: EarningUpdate,
    ctx: RequestCtx,
    svc: EarningsSvc,
):
    return await svc.edit_earning(ctx.user_id, earning_id, body)


@router.post("/classify/{transaction_id}")
async def classify_transaction(
    transaction_id: uuid.UUID,
    body: ClassifyTransactionRequest,
    ctx: RequestCtx,
    svc: EarningsSvc,
):
    await svc.classify_transaction(ctx.user_id, transaction_id, body)
    return {"status": "classified"}


@router.get("/sources", response_model=list[EarningSourceResponse])
async def get_sources(ctx: RequestCtx, svc: EarningsSvc):
    return await svc.list_sources(ctx.user_id)


@router.post(
    "/sources",
    response_model=EarningSourceResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_source(
    body: EarningSourceCreate,
    ctx: RequestCtx,
    svc: EarningsSvc,
):
    return await svc.add_source(ctx.user_id, body)


@router.patch("/sources/{source_id}", response_model=EarningSourceResponse)
async def edit_source(
    source_id: uuid.UUID,
    body: EarningSourceUpdate,
    ctx: RequestCtx,
    svc: EarningsSvc,
):
    return await svc.edit_source(ctx.user_id, source_id, body)


@router.delete("/sources/{source_id}", status_code=status.HTTP_204_NO_CONTENT)
async def deactivate_source(
    source_id: uuid.UUID,
    ctx: RequestCtx,
    svc: EarningsSvc,
):
    await svc.deactivate_source(ctx.user_id, source_id)
