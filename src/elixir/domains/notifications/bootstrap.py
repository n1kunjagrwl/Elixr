from elixir.shared.events import EventBus


def register_event_handlers(event_bus: EventBus) -> None:
    """Subscribe all 8 notification handlers to their respective events."""
    from elixir.domains.notifications.events import (
        handle_account_linked,
        handle_budget_limit_breached,
        handle_budget_limit_warning,
        handle_earning_classification_needed,
        handle_extraction_completed,
        handle_extraction_partially_completed,
        handle_import_completed,
        handle_sip_detected,
    )

    event_bus.subscribe("accounts.AccountLinked", handle_account_linked)
    event_bus.subscribe("statements.ExtractionCompleted", handle_extraction_completed)
    event_bus.subscribe(
        "statements.ExtractionPartiallyCompleted", handle_extraction_partially_completed
    )
    event_bus.subscribe(
        "earnings.EarningClassificationNeeded", handle_earning_classification_needed
    )
    event_bus.subscribe("investments.SIPDetected", handle_sip_detected)
    event_bus.subscribe("budgets.BudgetLimitWarning", handle_budget_limit_warning)
    event_bus.subscribe("budgets.BudgetLimitBreached", handle_budget_limit_breached)
    event_bus.subscribe("import_.ImportCompleted", handle_import_completed)
    # No outbox table registered — notifications domain is a pure event consumer


def get_temporal_workflows() -> list:
    return []


def get_temporal_activities(*args: object) -> list:
    return []
