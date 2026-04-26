"""
Temporal activities for the fx domain.

Activities are thin wrappers that call FXService methods with a real
DB session and exchangerate client. The business logic lives in
FXService.refresh_rates() and is tested at the service layer.
"""

from temporalio import activity


@activity.defn
async def fetch_and_upsert_fx_rates(currencies: list[str]) -> None:
    """
    Temporal activity stub: fetch rates for *currencies* and upsert into fx_rates.

    Full implementation requires injected session_factory and exchangerate_client,
    which are provided by the Temporal worker at startup (not unit-tested here;
    see FXService.refresh_rates() service tests instead).
    """
    # Implementation wired at worker startup via dependency injection.
    pass
