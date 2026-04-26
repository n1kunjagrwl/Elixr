"""
Integration test fixtures.

These tests use a real PostgreSQL container via testcontainers.
They are SLOW (container startup ~10s) and should be run separately from unit tests:
    uv run pytest tests/integration/ -v
"""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import AsyncGenerator
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from testcontainers.postgres import PostgresContainer

from elixir.shared.config import Settings
from elixir.shared.events import EventBus
from elixir.shared.outbox import OutboxPoller


POSTGRES_IMAGE = "postgres:16-alpine"


# ── Container (session-scoped — one container per pytest session) ──────────────

@pytest.fixture(scope="session")
def postgres_container():
    """Start a PostgreSQL container for the entire test session."""
    with PostgresContainer(POSTGRES_IMAGE) as pg:
        yield pg


# ── Settings pointing at the test container ───────────────────────────────────

@pytest.fixture(scope="session")
def integration_settings(postgres_container: PostgresContainer) -> Settings:
    """Settings pointed at the test PostgreSQL container.

    testcontainers.get_connection_url() returns a psycopg2 URL
    (e.g. ``postgresql+psycopg2://user:pass@host:port/db``).
    We replace the driver component so SQLAlchemy uses asyncpg.
    """
    import re

    raw_url = postgres_container.get_connection_url()
    # Replace any existing driver suffix (psycopg2, psycopg, etc.) with asyncpg,
    # or add asyncpg if the URL has no driver.
    db_url = re.sub(
        r"^postgresql\+\w+://",
        "postgresql+asyncpg://",
        raw_url,
    )
    # If no driver was present (plain postgresql://), add asyncpg.
    if not db_url.startswith("postgresql+asyncpg://"):
        db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)

    return Settings(
        database_url=db_url,
        jwt_secret="integration-test-secret-32-chars-long",
        encryption_key="a" * 64,
        twilio_account_sid="test",
        twilio_auth_token="test",
        twilio_verify_service_sid="test",
        temporal_address="localhost:7233",
        outbox_poll_interval_seconds=9999,   # effectively disable polling in tests
        otp_rate_limit_count=100,            # generous limit so tests don't hit it
        otp_rate_limit_window_minutes=60,
        otp_expiry_seconds=300,              # 5 min expiry gives tests room to breathe
    )


# ── Run Alembic migrations once before any integration test ───────────────────

@pytest.fixture(scope="session", autouse=True)
def run_migrations(postgres_container: PostgresContainer, integration_settings: Settings):
    """Run Alembic migrations against the test DB before any integration test runs.

    Uses the Alembic programmatic API to inject the test container URL without
    modifying alembic.ini or needing env.py to support -x args.
    """
    from alembic import command
    from alembic.config import Config

    project_root = "/Users/nikunjagarwal/Documents/Programs/Projects/Elixir"

    # Alembic env.py uses async engine; we provide the async URL directly.
    # env.py reads via `config.get_main_option("sqlalchemy.url")`.
    alembic_cfg = Config(f"{project_root}/alembic.ini")
    alembic_cfg.set_main_option("script_location", f"{project_root}/alembic")
    alembic_cfg.set_main_option("sqlalchemy.url", integration_settings.database_url)

    command.upgrade(alembic_cfg, "head")


# ── FastAPI app wired to the real DB, with external services mocked ───────────

@pytest_asyncio.fixture
async def integration_app(integration_settings: Settings):
    """
    A real FastAPI app wired to the test PostgreSQL container.
    Temporal and Twilio are mocked so no external services are needed.

    The app uses a custom lifespan that sets up only the real DB engine and
    EventBus/OutboxPoller, leaving all third-party clients as mocks.
    """
    from fastapi import FastAPI
    from elixir.runtime.app import _mount_routers, _register_exception_handlers
    from elixir.platform.db import build_engine, build_session_factory

    # Track OTPs emitted so tests can retrieve them.
    last_otp: dict[str, str] = {}

    # temporal_client is set to None in the lifespan so IdentityService falls back
    # to direct twilio.send_otp(), allowing OTP capture in tests.

    mock_twilio = AsyncMock()

    async def _capture_otp(phone: str, otp_code: str) -> None:  # type: ignore[return]
        last_otp["code"] = otp_code

    mock_twilio.send_otp = AsyncMock(side_effect=_capture_otp)

    @asynccontextmanager
    async def _integration_lifespan(app: FastAPI):
        settings: Settings = app.state.settings

        # Real database
        engine = build_engine(settings.database_url)
        session_factory = build_session_factory(engine)
        app.state.engine = engine
        app.state.session_factory = session_factory

        # Temporal — None so IdentityService falls back to direct Twilio call
        app.state.temporal_client = None

        # File storage — not needed for auth tests
        app.state.storage = None

        # Mocked platform clients
        app.state.twilio = mock_twilio
        app.state.amfi = AsyncMock()
        app.state.coingecko = AsyncMock()
        app.state.eodhd = AsyncMock()
        app.state.twelve_data = AsyncMock()
        app.state.metals_api = AsyncMock()
        app.state.exchangerate = AsyncMock()

        # EventBus + domain bootstrap
        event_bus = EventBus()
        app.state.event_bus = event_bus

        from elixir.domains.identity import bootstrap as identity_b
        from elixir.domains.accounts import bootstrap as accounts_b
        from elixir.domains.transactions import bootstrap as transactions_b
        from elixir.domains.categorization import bootstrap as cat_b
        from elixir.domains.investments import bootstrap as investments_b
        from elixir.domains.earnings import bootstrap as earnings_b
        from elixir.domains.budgets import bootstrap as budgets_b
        from elixir.domains.peers import bootstrap as peers_b
        from elixir.domains.notifications import bootstrap as notifications_b
        from elixir.domains.fx import bootstrap as fx_b
        from elixir.domains.statements import bootstrap as statements_b
        from elixir.domains.import_ import bootstrap as import_b

        for module in [
            identity_b, accounts_b, transactions_b, cat_b, investments_b,
            earnings_b, budgets_b, peers_b, notifications_b, fx_b,
            statements_b, import_b,
        ]:
            module.register_event_handlers(event_bus)

        # OutboxPoller with a huge interval so it doesn't fire during tests
        outbox_poller = OutboxPoller(
            session_factory=session_factory,
            event_bus=event_bus,
            poll_interval_seconds=settings.outbox_poll_interval_seconds,
        )
        poller_task = asyncio.create_task(outbox_poller.run())

        yield

        poller_task.cancel()
        try:
            await poller_task
        except asyncio.CancelledError:
            pass

        await engine.dispose()

    app = FastAPI(
        title="Elixir Integration Tests",
        lifespan=_integration_lifespan,
    )
    app.state.settings = integration_settings
    # Expose last_otp for tests to read
    app.state._last_otp = last_otp

    _mount_routers(app)
    _register_exception_handlers(app)

    from elixir.runtime.middleware import AuthMiddleware, RequestLoggingMiddleware

    # CORS not needed for integration tests (httpx doesn't enforce it).
    # Keep AuthMiddleware and RequestLoggingMiddleware so the full middleware
    # stack matches production behaviour.
    app.add_middleware(RequestLoggingMiddleware)
    app.add_middleware(AuthMiddleware)

    yield app


@pytest_asyncio.fixture
async def integration_client(integration_app) -> AsyncGenerator[AsyncClient, None]:
    """httpx AsyncClient connected to the integration test app."""
    async with AsyncClient(
        transport=ASGITransport(app=integration_app),
        base_url="http://testserver",
    ) as client:
        yield client
