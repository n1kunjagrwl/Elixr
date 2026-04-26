from elixir.shared.events import EventBus


def register_event_handlers(event_bus: EventBus) -> None:
    from elixir.domains.investments.events import (
        handle_account_removed,
        handle_transaction_created,
    )

    event_bus.subscribe("accounts.AccountRemoved", handle_account_removed)
    event_bus.subscribe("transactions.TransactionCreated", handle_transaction_created)
    event_bus.register_outbox_table("investments_outbox")


def get_temporal_workflows() -> list:
    return []


def get_temporal_activities(*args) -> list:
    return []
