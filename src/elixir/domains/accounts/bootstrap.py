from elixir.shared.events import EventBus


def register_event_handlers(event_bus: EventBus) -> None:
    from elixir.domains.accounts.events import handle_account_linked, handle_account_removed

    event_bus.subscribe("accounts.AccountLinked", handle_account_linked)
    event_bus.subscribe("accounts.AccountRemoved", handle_account_removed)
    event_bus.register_outbox_table("accounts_outbox")


def get_temporal_workflows() -> list:
    return []


def get_temporal_activities(*args) -> list:
    return []
