from elixir.shared.events import EventBus


def register_event_handlers(event_bus: EventBus) -> None:
    """Register statements domain event handlers and outbox table."""
    event_bus.register_outbox_table("statements_outbox")


def get_temporal_workflows() -> list:
    from elixir.domains.statements.workflows.statement_processing import (
        StatementProcessingWorkflow,
    )
    return [StatementProcessingWorkflow]


def get_temporal_activities(*args) -> list:
    return []
