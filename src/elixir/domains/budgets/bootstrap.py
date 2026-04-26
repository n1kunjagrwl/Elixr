from elixir.shared.events import EventBus


def register_event_handlers(event_bus: EventBus) -> None:
    """Register budgets domain event handlers with the event bus."""
    from elixir.domains.budgets.events import (
        handle_transaction_categorized,
        handle_transaction_updated,
    )

    event_bus.subscribe(
        "transactions.TransactionCategorized",
        handle_transaction_categorized,
    )
    event_bus.subscribe(
        "transactions.TransactionUpdated",
        handle_transaction_updated,
    )
    event_bus.register_outbox_table("budgets_outbox")


def get_temporal_workflows() -> list:
    return []


def get_temporal_activities(*args: object) -> list:
    return []
