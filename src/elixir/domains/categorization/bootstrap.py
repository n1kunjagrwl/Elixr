from elixir.shared.events import EventBus


def register_event_handlers(event_bus: EventBus) -> None:
    """Register categorization domain event handlers with the event bus."""
    from elixir.domains.categorization.events import handle_category_created

    event_bus.subscribe(
        "categorization.CategoryCreated",
        handle_category_created,
    )
    event_bus.register_outbox_table("categorization_outbox")
