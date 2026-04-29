from dataclasses import dataclass

from temporalio import activity

from elixir.platform.clients.twilio import TwilioClient


@dataclass
class OTPDeliveryInput:
    phone_e164: str


class OTPDeliveryActivities:
    """
    Class-based activities enable constructor injection of platform clients.
    The worker registers bound methods (e.g., activities.send_otp_via_twilio).
    """

    def __init__(self, twilio: TwilioClient) -> None:
        self._twilio = twilio

    @activity.defn
    async def send_otp_via_twilio(self, input: OTPDeliveryInput) -> None:
        await self._twilio.send_otp(input.phone_e164)
