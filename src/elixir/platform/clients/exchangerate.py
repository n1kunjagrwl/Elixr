import logging

import httpx

from elixir.shared.config import Settings

logger = logging.getLogger(__name__)

_BASE = "https://v6.exchangerate-api.com/v6"


class ExchangeRateClient:
    def __init__(self, settings: Settings) -> None:
        self._api_key = settings.exchangerate_api_key
        self._client = httpx.AsyncClient(timeout=15.0)

    async def get_rates(self, base_currency: str = "INR") -> dict[str, float]:
        """Returns all rates with base_currency as 1.0."""
        resp = await self._client.get(f"{_BASE}/{self._api_key}/latest/{base_currency}")
        resp.raise_for_status()
        return resp.json()["conversion_rates"]

    async def close(self) -> None:
        await self._client.aclose()
