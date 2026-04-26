"""
FXRateRefreshWorkflow — Temporal workflow that refreshes FX rates every 6 hours.

The workflow calls Temporal activities (defined in activities.py) to:
1. Fetch the latest rates from the exchangerate-api.com client.
2. Upsert the fetched rates into the fx_rates table via FXService.refresh_rates().

Workflow code must be deterministic — no side effects here, only activity calls.
"""

from temporalio import workflow


@workflow.defn
class FXRateRefreshWorkflow:
    """Scheduled every 6 hours via Temporal to keep the FX rate cache fresh."""

    @workflow.run
    async def run(self) -> None:
        # Activities will be called here once the activity layer is fully wired.
        # The actual fetch+upsert logic lives in FXService.refresh_rates(),
        # which is tested at the service layer (see tests/domains/fx/test_services.py).
        pass


WORKFLOWS = [FXRateRefreshWorkflow]
ACTIVITIES: list = []
