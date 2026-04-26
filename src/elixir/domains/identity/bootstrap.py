from elixir.shared.events import EventBus


def register_event_handlers(event_bus: EventBus) -> None:
    from elixir.domains.identity.events import handle_user_logged_in, handle_user_registered

    event_bus.subscribe("identity.UserRegistered", handle_user_registered)
    event_bus.subscribe("identity.UserLoggedIn", handle_user_logged_in)
    event_bus.register_outbox_table("identity_outbox")


def get_temporal_workflows() -> list:
    from elixir.domains.identity.workflows.otp_delivery import OTPDeliveryWorkflow
    return [OTPDeliveryWorkflow]


def get_temporal_activities(twilio) -> list:
    from elixir.domains.identity.workflows.activities import OTPDeliveryActivities
    activities = OTPDeliveryActivities(twilio=twilio)
    return [activities.send_otp_via_twilio]
