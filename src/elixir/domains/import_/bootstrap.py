from elixir.shared.events import EventBus


def register_event_handlers(event_bus: EventBus) -> None:
    event_bus.register_outbox_table("import_outbox")


def get_temporal_workflows() -> list:
    from elixir.domains.import_.workflows.import_processing import (
        ImportProcessingWorkflow,
    )

    return [ImportProcessingWorkflow]


def get_temporal_activities(*args) -> list:
    return []
