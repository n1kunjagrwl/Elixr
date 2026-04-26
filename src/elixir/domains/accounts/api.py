import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Request, status

from elixir.domains.accounts.schemas import (
    AccountSummaryResponse,
    BankAccountCreate,
    BankAccountResponse,
    BankAccountUpdate,
    CreditCardCreate,
    CreditCardResponse,
    CreditCardUpdate,
)
from elixir.domains.accounts.services import AccountsService
from elixir.runtime.dependencies import RequestCtx, get_db_session

router = APIRouter()


# ── Service factory ───────────────────────────────────────────────────────────

def get_accounts_service(
    request: Request,
    db=Depends(get_db_session),
) -> AccountsService:
    return AccountsService(
        db=db,
        settings=request.app.state.settings,
    )


AccountsSvc = Annotated[AccountsService, Depends(get_accounts_service)]


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("", response_model=list[AccountSummaryResponse])
async def get_accounts(ctx: RequestCtx, svc: AccountsSvc):
    """List all active accounts for the authenticated user."""
    return await svc.list_accounts(ctx.user_id)


@router.post("/bank", response_model=BankAccountResponse, status_code=status.HTTP_201_CREATED)
async def add_bank_account(
    body: BankAccountCreate,
    ctx: RequestCtx,
    svc: AccountsSvc,
):
    """Add a new bank account for the authenticated user."""
    return await svc.add_bank_account(ctx.user_id, body)


@router.post(
    "/credit-cards", response_model=CreditCardResponse, status_code=status.HTTP_201_CREATED
)
async def add_credit_card(
    body: CreditCardCreate,
    ctx: RequestCtx,
    svc: AccountsSvc,
):
    """Add a new credit card for the authenticated user."""
    return await svc.add_credit_card(ctx.user_id, body)


@router.patch("/bank/{account_id}", response_model=BankAccountResponse)
async def edit_bank_account(
    account_id: uuid.UUID,
    body: BankAccountUpdate,
    ctx: RequestCtx,
    svc: AccountsSvc,
):
    """Partially update a bank account owned by the authenticated user."""
    return await svc.edit_bank_account(ctx.user_id, account_id, body)


@router.patch("/credit-cards/{card_id}", response_model=CreditCardResponse)
async def edit_credit_card(
    card_id: uuid.UUID,
    body: CreditCardUpdate,
    ctx: RequestCtx,
    svc: AccountsSvc,
):
    """Partially update a credit card owned by the authenticated user."""
    return await svc.edit_credit_card(ctx.user_id, card_id, body)


@router.delete("/bank/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
async def deactivate_bank_account(
    account_id: uuid.UUID,
    ctx: RequestCtx,
    svc: AccountsSvc,
):
    """Soft-delete (deactivate) a bank account owned by the authenticated user."""
    await svc.deactivate_bank_account(ctx.user_id, account_id)


@router.delete("/credit-cards/{card_id}", status_code=status.HTTP_204_NO_CONTENT)
async def deactivate_credit_card(
    card_id: uuid.UUID,
    ctx: RequestCtx,
    svc: AccountsSvc,
):
    """Soft-delete (deactivate) a credit card owned by the authenticated user."""
    await svc.deactivate_credit_card(ctx.user_id, card_id)
