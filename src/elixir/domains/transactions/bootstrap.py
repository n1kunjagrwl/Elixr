from elixir.shared.events import EventBus


def register_event_handlers(event_bus: EventBus) -> None:
    from elixir.domains.transactions.events import (
        handle_extraction_completed,
        handle_extraction_partially_completed,
        handle_import_batch_ready,
    )

    event_bus.subscribe("statements.ExtractionCompleted", handle_extraction_completed)
    event_bus.subscribe(
        "statements.ExtractionPartiallyCompleted",
        handle_extraction_partially_completed,
    )
    event_bus.subscribe("import_.ImportBatchReady", handle_import_batch_ready)
    event_bus.register_outbox_table("transactions_outbox")


def get_temporal_workflows() -> list:
    from elixir.domains.transactions.workflows.recurring_detection import (
        RecurringTransactionDetectionWorkflow,
    )

    return [RecurringTransactionDetectionWorkflow]


def get_temporal_activities(*args) -> list:
    return []
