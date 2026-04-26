import logging

import httpx

from elixir.shared.config import Settings
from elixir.shared.exceptions import TwilioError

logger = logging.getLogger(__name__)


class TwilioClient:
    def __init__(self, settings: Settings) -> None:
        self._account_sid = settings.twilio_account_sid
        self._auth_token = settings.twilio_auth_token
        self._verify_sid = settings.twilio_verify_service_sid
        self._client = httpx.AsyncClient(
            base_url="https://verify.twilio.com/v2",
            auth=(settings.twilio_account_sid, settings.twilio_auth_token),
            timeout=10.0,
        )

    async def send_otp(self, phone_e164: str, otp_code: str) -> None:
        """Send OTP via Twilio Verify custom code."""
        try:
            resp = await self._client.post(
                f"/Services/{self._verify_sid}/Verifications",
                data={"To": phone_e164, "Channel": "sms", "CustomCode": otp_code},
            )
            resp.raise_for_status()
        except httpx.HTTPStatusError as exc:
            logger.error("Twilio send_otp failed: %s", exc.response.text)
            raise TwilioError(f"Failed to send OTP: {exc.response.status_code}")
        except httpx.RequestError as exc:
            logger.error("Twilio request error: %s", exc)
            raise TwilioError("Twilio connection error")

    async def close(self) -> None:
        await self._client.aclose()
