"""Temporal worker entrypoint. Run with: python -m elixir.platform.worker"""

import asyncio
import logging
from temporalio.worker import Worker

logger = logging.getLogger(__name__)


async def run_worker() -> None:
    from elixir.shared.config import Settings

    settings = Settings()

    from elixir.platform.temporal import build_temporal_client

    client = await build_temporal_client(
        settings.temporal_address, settings.temporal_namespace
    )

    from elixir.platform.db import build_engine, build_session_factory

    engine = build_engine(settings.database_url)
    session_factory = build_session_factory(engine)

    # Collect all workflows and activities from domain packages
    workflows, activities = _collect_all(session_factory, settings)

    worker = Worker(
        client,
        task_queue=settings.temporal_task_queue,
        workflows=workflows,
        activities=activities,
    )
    logger.info("Temporal worker starting on queue: %s", settings.temporal_task_queue)
    await worker.run()


def _collect_all(session_factory, settings) -> tuple[list, list]:
    """Import and return all workflow classes and activity functions from domain packages."""
    workflows = []
    activities = []

    # Identity: OTP delivery activities require a live TwilioClient — inject it here.
    try:
        from elixir.domains.identity.workflows.otp_delivery import OTPDeliveryWorkflow
        from elixir.domains.identity.workflows.activities import OTPDeliveryActivities
        from elixir.platform.clients.twilio import TwilioClient

        twilio = TwilioClient(settings)
        otp_activities = OTPDeliveryActivities(twilio)
        workflows.append(OTPDeliveryWorkflow)
        activities.append(otp_activities.send_otp_via_twilio)
    except Exception as exc:
        logger.warning("Could not load identity OTP workflow: %s", exc)
    _safe_collect(workflows, activities, "elixir.domains.fx.workflows.fx_rate_refresh")
    _safe_collect(
        workflows,
        activities,
        "elixir.domains.statements.workflows.statement_processing",
    )
    _safe_collect(
        workflows,
        activities,
        "elixir.domains.transactions.workflows.recurring_detection",
    )
    _safe_collect(
        workflows, activities, "elixir.domains.import_.workflows.import_processing"
    )
    _safe_collect(
        workflows, activities, "elixir.domains.investments.workflows.market_price_fetch"
    )
    _safe_collect(
        workflows,
        activities,
        "elixir.domains.investments.workflows.calculated_valuation",
    )

    return workflows, activities


def _safe_collect(workflows: list, activities: list, module_path: str) -> None:
    try:
        import importlib

        mod = importlib.import_module(module_path)
        if hasattr(mod, "WORKFLOWS"):
            workflows.extend(mod.WORKFLOWS)
        if hasattr(mod, "ACTIVITIES"):
            activities.extend(mod.ACTIVITIES)
    except Exception as exc:
        logger.warning("Could not load workflow module %s: %s", module_path, exc)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_worker())
