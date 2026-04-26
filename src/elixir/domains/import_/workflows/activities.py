from temporalio import activity


@activity.defn
async def detect_columns_activity(file_path: str, source_type: str) -> list[dict]:
    """
    Activity stub for import column detection.

    The concrete parsing and rule application logic will be wired once the
    storage and categorization integrations are implemented for workflow runs.
    """
    return []
