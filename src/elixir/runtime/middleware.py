import logging
import time
import uuid
from uuid import UUID

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from elixir.shared.exceptions import TokenExpiredError, TokenInvalidError

logger = logging.getLogger(__name__)

_PUBLIC_PATHS = frozenset({
    "/auth/request-otp",
    "/auth/verify-otp",
    "/auth/refresh",
    "/health",
    "/docs",
    "/openapi.json",
    "/redoc",
})


class AuthMiddleware(BaseHTTPMiddleware):
    """
    Extracts Bearer token from Authorization header and decodes it.
    Stores user_id and session_id on request.state.
    Does NOT raise — unauthenticated requests are allowed through so that
    public routes work. Protected routes raise 401 via get_request_context().
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        if request.url.path in _PUBLIC_PATHS:
            request.state.user_id = None
            request.state.session_id = None
            return await call_next(request)

        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            token = auth.removeprefix("Bearer ")
            try:
                from elixir.shared.security import decode_access_token
                settings = request.app.state.settings
                claims = decode_access_token(token, settings.jwt_secret)
                request.state.user_id = UUID(claims["sub"])
                request.state.session_id = UUID(claims["sid"])
            except (TokenExpiredError, TokenInvalidError):
                request.state.user_id = None
                request.state.session_id = None
        else:
            request.state.user_id = None
            request.state.session_id = None

        return await call_next(request)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Logs every request with method, path, status code, and duration."""

    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.state.request_id = request_id
        start = time.perf_counter()

        response = await call_next(request)

        duration_ms = (time.perf_counter() - start) * 1000
        logger.info(
            "%s %s %d %.1fms",
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
            extra={
                "request_id": request_id,
                "user_id": str(getattr(request.state, "user_id", None)),
            },
        )
        response.headers["X-Request-ID"] = request_id
        return response
