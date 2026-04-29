import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from elixir.platform.db import build_engine, build_session_factory
from elixir.platform.temporal import build_temporal_client
from elixir.platform.clients.amfi import AMFIClient
from elixir.platform.clients.coingecko import CoinGeckoClient
from elixir.platform.clients.eodhd import EodhdClient
from elixir.platform.clients.exchangerate import ExchangeRateClient
from elixir.platform.clients.metals_api import MetalsAPIClient
from elixir.platform.clients.twelve_data import TwelveDataClient
from elixir.platform.clients.twilio import TwilioClient
from elixir.shared.config import Settings
from elixir.shared.events import EventBus
from elixir.shared.outbox import OutboxPoller

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings: Settings = app.state.settings

    logger.info("Starting Elixr...")

    # 1. Database
    engine = build_engine(
        settings.database_url,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        pool_recycle=settings.db_pool_recycle,
        pool_timeout=settings.db_pool_timeout,
        statement_timeout_ms=settings.db_statement_timeout_ms,
    )
    session_factory = build_session_factory(engine)
    app.state.engine = engine
    app.state.session_factory = session_factory

    # 2. Temporal
    try:
        temporal_client = await build_temporal_client(
            settings.temporal_address,
            settings.temporal_namespace,
            tls=settings.temporal_tls,
        )
        app.state.temporal_client = temporal_client
        logger.info("Connected to Temporal at %s", settings.temporal_address)
    except Exception:
        logger.warning(
            "Could not connect to Temporal — workflows disabled", exc_info=True
        )
        app.state.temporal_client = None

    # 3. File storage
    # Storage deferred — file upload endpoints will raise StorageUnavailableError
    app.state.storage = None

    # 4. Platform clients
    app.state.twilio = TwilioClient(settings)
    app.state.amfi = AMFIClient(settings)
    app.state.coingecko = CoinGeckoClient(settings)
    app.state.eodhd = EodhdClient(settings)
    app.state.twelve_data = TwelveDataClient(settings)
    app.state.metals_api = MetalsAPIClient(settings)
    app.state.exchangerate = ExchangeRateClient(settings)

    # 5. EventBus
    event_bus = EventBus()
    app.state.event_bus = event_bus

    # 6. Bootstrap all domains (registers event handlers, outbox tables)
    _bootstrap_domains(event_bus)

    # 7. Outbox poller
    outbox_poller = OutboxPoller(
        session_factory=session_factory,
        event_bus=event_bus,
        poll_interval_seconds=settings.outbox_poll_interval_seconds,
    )
    poller_task = asyncio.create_task(outbox_poller.run())

    logger.info("Elixr started successfully")
    yield

    # ── SHUTDOWN ──────────────────────────────────────────────────────
    logger.info("Shutting down Elixr...")
    poller_task.cancel()
    try:
        await poller_task
    except asyncio.CancelledError:
        pass

    await engine.dispose()

    if app.state.temporal_client:
        app.state.temporal_client.close()

    for client_name in (
        "twilio",
        "amfi",
        "coingecko",
        "eodhd",
        "twelve_data",
        "metals_api",
        "exchangerate",
    ):
        client = getattr(app.state, client_name, None)
        if client and hasattr(client, "close"):
            await client.close()

    logger.info("Elixr stopped")


def _bootstrap_domains(event_bus: EventBus) -> None:
    """
    Import each domain's bootstrap module and register its event handlers.
    Deferred to inside lifespan() to avoid circular imports at module load time.
    """
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
        identity_b,
        accounts_b,
        transactions_b,
        cat_b,
        investments_b,
        earnings_b,
        budgets_b,
        peers_b,
        notifications_b,
        fx_b,
        statements_b,
        import_b,
    ]:
        module.register_event_handlers(event_bus)
