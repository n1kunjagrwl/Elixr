from elixir.shared.events import EventBus


def register_event_handlers(event_bus: EventBus) -> None:
    # peers domain publishes no events and subscribes to none.
    # PeerContact names are exposed cross-domain via the peer_contacts_public SQL view (Pattern 1).
    pass


def get_temporal_workflows() -> list:
    return []


def get_temporal_activities(*args) -> list:
    return []
