from temporalio import activity


@activity.defn
async def scan_for_recurring_transactions() -> None:
    """
    Workflow activity stub for recurring transaction detection.

    The business logic belongs in the transactions service/repository layer and
    will be wired into the Temporal worker when the workflow is executed for
    real infrastructure-backed runs.
    """
    pass
