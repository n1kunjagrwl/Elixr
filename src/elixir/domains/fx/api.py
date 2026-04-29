from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import JSONResponse

from elixir.domains.fx.schemas import ConvertResponse, FXRateResponse
from elixir.domains.fx.services import FXService
from elixir.runtime.dependencies import RequestCtx, get_db_session
from elixir.shared.exceptions import FXRateUnavailableError

router = APIRouter()


# ── Service factory ───────────────────────────────────────────────────────────


def get_fx_service(
    db=Depends(get_db_session),
) -> FXService:
    return FXService(db=db)


FXSvc = Annotated[FXService, Depends(get_fx_service)]


# ── Endpoints ─────────────────────────────────────────────────────────────────


@router.get("/rates", response_model=list[FXRateResponse])
async def get_rates(ctx: RequestCtx, svc: FXSvc):
    """List all currently cached FX rates."""
    rates = await svc.list_rates()
    return [FXRateResponse.model_validate(r) for r in rates]


@router.get("/convert", response_model=ConvertResponse)
async def convert_currency(
    ctx: RequestCtx,
    svc: FXSvc,
    amount: Decimal = Query(..., description="Amount to convert"),
    from_currency: str = Query(
        ..., alias="from", description="Source currency code (e.g. USD)"
    ),
    to_currency: str = Query(
        ..., alias="to", description="Target currency code (e.g. INR)"
    ),
):
    """
    Convert an amount between two currencies using the cached FX rates.

    Returns 503 if no cached rate is available for the requested pair.
    """
    try:
        result = await svc.convert_with_meta(
            amount=amount,
            from_currency=from_currency.upper(),
            to_currency=to_currency.upper(),
        )
    except FXRateUnavailableError as exc:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"error": exc.error_code, "detail": exc.detail},
        )
    return result
