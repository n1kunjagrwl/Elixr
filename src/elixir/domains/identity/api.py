from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response, status

from elixir.domains.identity.schemas import (
    OTPRequestedResponse,
    RefreshResponse,
    RequestOTPBody,
    VerifyOTPBody,
    VerifyOTPResponse,
)
from elixir.domains.identity.services import IdentityService, IdentityServiceProtocol
from elixir.runtime.dependencies import RequestCtx, get_db_session

router = APIRouter()

_REFRESH_COOKIE = "refresh_token"
_COOKIE_MAX_AGE = 7 * 24 * 60 * 60  # 7 days in seconds


# ── Service factory ───────────────────────────────────────────────────


def get_identity_service(
    request: Request,
    db=Depends(get_db_session),
) -> IdentityServiceProtocol:
    return IdentityService(
        db=db,
        twilio=request.app.state.twilio,
        temporal_client=request.app.state.temporal_client,
        settings=request.app.state.settings,
    )


IdentitySvc = Annotated[IdentityServiceProtocol, Depends(get_identity_service)]


# ── Endpoints ─────────────────────────────────────────────────────────


@router.post("/request-otp", response_model=OTPRequestedResponse)
async def request_otp(body: RequestOTPBody, svc: IdentitySvc):
    return await svc.request_otp(body.phone)


@router.post("/verify-otp", response_model=VerifyOTPResponse)
async def verify_otp(body: VerifyOTPBody, request: Request, response: Response, svc: IdentitySvc):
    result = await svc.verify_otp(body.phone, body.otp)
    secure = request.app.state.settings.cookie_secure
    response.set_cookie(
        key=_REFRESH_COOKIE,
        value=result.refresh_token,
        httponly=True,
        secure=secure,
        samesite="strict",
        max_age=_COOKIE_MAX_AGE,
    )
    return VerifyOTPResponse(access_token=result.access_token)


@router.post("/refresh", response_model=RefreshResponse)
async def refresh(request: Request, svc: IdentitySvc):
    refresh_token = request.cookies.get(_REFRESH_COOKIE)
    from fastapi import HTTPException

    if not refresh_token:
        raise HTTPException(status_code=401, detail="No refresh token provided")
    return await svc.refresh_session(refresh_token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(request: Request, ctx: RequestCtx, response: Response, svc: IdentitySvc):
    await svc.logout(ctx.user_id, ctx.session_id)
    secure = request.app.state.settings.cookie_secure
    response.delete_cookie(
        key=_REFRESH_COOKIE, httponly=True, secure=secure, samesite="strict"
    )
