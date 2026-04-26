from elixir.shared.events import EventBus


def register_event_handlers(event_bus: EventBus) -> None:
    from elixir.domains.earnings.events import handle_transaction_created

    event_bus.subscribe("transactions.TransactionCreated", handle_transaction_created)
    event_bus.register_outbox_table("earnings_outbox")


def get_temporal_workflows() -> list:
    return []


def get_temporal_activities(*args) -> list:
    return []
