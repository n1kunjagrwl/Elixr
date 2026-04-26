import logging
from collections.abc import Mapping, Sequence

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from elixir.shared.config import Settings
from elixir.shared.exceptions import ElixirError
from elixir.runtime.lifespan import lifespan
from elixir.runtime.middleware import AuthMiddleware, RequestLoggingMiddleware

logger = logging.getLogger(__name__)


def create_app(settings: Settings | None = None) -> FastAPI:
    if settings is None:
        settings = Settings()

    app = FastAPI(
        title="Elixr",
        version="0.1.0",
        description="Multi-user personal finance manager",
        lifespan=lifespan,
        redirect_slashes=False,
    )
    app.state.settings = settings

    # ── MIDDLEWARE (outermost → innermost) ────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(RequestLoggingMiddleware)
    app.add_middleware(AuthMiddleware)

    # ── DOMAIN ROUTERS ────────────────────────────────────────────────
    _mount_routers(app)

    # ── EXCEPTION HANDLERS ───────────────────────────────────────────
    _register_exception_handlers(app)

    # ── HEALTH CHECK ─────────────────────────────────────────────────
    @app.get("/health", tags=["health"])
    async def health():
        return {"status": "ok"}

    return app


def _mount_routers(app: FastAPI) -> None:
    from elixir.domains.identity.api import router as identity_router
    from elixir.domains.accounts.api import router as accounts_router
    from elixir.domains.transactions.api import router as transactions_router
    from elixir.domains.categorization.api import router as cat_router, rules_router as cat_rules_router
    from elixir.domains.investments.api import router as investments_router
    from elixir.domains.earnings.api import router as earnings_router
    from elixir.domains.budgets.api import router as budgets_router
    from elixir.domains.peers.api import router as peers_router
    from elixir.domains.notifications.api import router as notifications_router
    from elixir.domains.fx.api import router as fx_router
    from elixir.domains.statements.api import router as statements_router
    from elixir.domains.import_.api import router as import_router

    app.include_router(identity_router,      prefix="/auth",          tags=["auth"])
    app.include_router(accounts_router,      prefix="/accounts",      tags=["accounts"])
    app.include_router(transactions_router,  prefix="/transactions",  tags=["transactions"])
    app.include_router(cat_router,           prefix="/categories",           tags=["categorization"])
    app.include_router(cat_rules_router,     prefix="/categorization-rules", tags=["categorization"])
    app.include_router(investments_router,   prefix="/investments",   tags=["investments"])
    app.include_router(earnings_router,      prefix="/earnings",      tags=["earnings"])
    app.include_router(budgets_router,       prefix="/budgets",       tags=["budgets"])
    app.include_router(peers_router,         prefix="/peers",         tags=["peers"])
    app.include_router(notifications_router, prefix="/notifications", tags=["notifications"])
    app.include_router(fx_router,            prefix="/fx",            tags=["fx"])
    app.include_router(statements_router,    prefix="/statements",    tags=["statements"])
    app.include_router(import_router,        prefix="/import",        tags=["import"])


def _register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(ElixirError)
    async def elixir_error_handler(request: Request, exc: ElixirError) -> JSONResponse:
        if exc.http_status >= 500:
            logger.error(
                "ElixirError %s: %s",
                exc.error_code,
                exc.detail,
                extra={"request_id": getattr(request.state, "request_id", None), "context": exc.context},
                exc_info=exc,
            )
        return JSONResponse(
            status_code=exc.http_status,
            content={"error": exc.error_code, "detail": exc.detail},
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        # Pydantic v2 ctx.error is a live Exception — convert to str for JSON serialisation.
        def _serialisable(errors: Sequence[dict[str, object]]) -> list[dict]:
            safe = []
            for err in errors:
                entry = dict(err)
                if "ctx" in entry:
                    raw_ctx = entry["ctx"]
                    if isinstance(raw_ctx, Mapping):
                        ctx = dict(raw_ctx)
                        entry["ctx"] = {
                            k: str(v) if isinstance(v, Exception) else v
                            for k, v in ctx.items()
                        }
                safe.append(entry)
            return safe

        return JSONResponse(
            status_code=422,
            content={"error": "VALIDATION_ERROR", "detail": _serialisable(exc.errors())},
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception(
            "Unhandled exception on %s %s",
            request.method,
            request.url.path,
            extra={"request_id": getattr(request.state, "request_id", None)},
        )
        return JSONResponse(
            status_code=500,
            content={"error": "INTERNAL_ERROR", "detail": "An unexpected error occurred"},
        )
