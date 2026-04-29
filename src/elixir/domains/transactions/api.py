import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, status

from elixir.domains.transactions.schemas import (
    TransactionCreate,
    TransactionFilters,
    TransactionListResponse,
    TransactionResponse,
    TransactionSource,
    TransactionType,
    TransactionUpdate,
)
from elixir.domains.transactions.services import TransactionsService
from elixir.runtime.dependencies import RequestCtx, get_db_session

router = APIRouter()


def get_transactions_service(
    request: Request,
    db=Depends(get_db_session),
) -> TransactionsService:
    return TransactionsService(db=db, settings=request.app.state.settings)


TransactionsSvc = Annotated[TransactionsService, Depends(get_transactions_service)]


@router.get("", response_model=TransactionListResponse)
async def get_transactions(
    ctx: RequestCtx,
    svc: TransactionsSvc,
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    account_id: uuid.UUID | None = Query(default=None),
    type: TransactionType | None = Query(default=None),
    source: TransactionSource | None = Query(default=None),
    category_id: uuid.UUID | None = Query(default=None),
    search_text: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
):
    filters = TransactionFilters(
        date_from=date_from,
        date_to=date_to,
        account_id=account_id,
        type=type,
        source=source,
        category_id=category_id,
        search_text=search_text,
    )
    return await svc.list_transactions(
        ctx.user_id, filters=filters, page=page, page_size=page_size
    )


@router.get("/{transaction_id}", response_model=TransactionResponse)
async def get_transaction(
    transaction_id: uuid.UUID,
    ctx: RequestCtx,
    svc: TransactionsSvc,
):
    return await svc.get_transaction(ctx.user_id, transaction_id)


@router.post(
    "", response_model=TransactionResponse, status_code=status.HTTP_201_CREATED
)
async def add_transaction(
    body: TransactionCreate,
    ctx: RequestCtx,
    svc: TransactionsSvc,
):
    return await svc.add_transaction(ctx.user_id, body)


@router.patch("/{transaction_id}", response_model=TransactionResponse)
async def edit_transaction(
    transaction_id: uuid.UUID,
    body: TransactionUpdate,
    ctx: RequestCtx,
    svc: TransactionsSvc,
):
    return await svc.edit_transaction(ctx.user_id, transaction_id, body)
