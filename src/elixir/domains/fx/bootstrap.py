from elixir.shared.events import EventBus


def register_event_handlers(event_bus: EventBus) -> None:
    pass  # fx domain has no outbox and subscribes to no events


def get_temporal_workflows() -> list:
    from elixir.domains.fx.workflows.fx_rate_refresh import FXRateRefreshWorkflow

    return [FXRateRefreshWorkflow]


def get_temporal_activities(exchangerate_client, session_factory) -> list:
    return []  # activities stubbed; logic tested via service tests
