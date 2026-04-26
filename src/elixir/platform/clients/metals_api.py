import logging

import httpx

from elixir.shared.config import Settings

logger = logging.getLogger(__name__)

_BASE = "https://metals-api.com/api"


class MetalsAPIClient:
    def __init__(self, settings: Settings) -> None:
        self._api_key = settings.metals_api_key
        self._client = httpx.AsyncClient(base_url=_BASE, timeout=15.0)

    async def get_gold_price_inr_per_gram(self) -> float:
        """Returns gold spot price in INR per gram."""
        resp = await self._client.get(
            "/latest",
            params={"access_key": self._api_key, "base": "INR", "symbols": "XAU"},
        )
        resp.raise_for_status()
        data = resp.json()
        troy_oz_to_gram = 31.1035
        price_per_troy_oz = 1.0 / data["rates"]["XAU"]
        return price_per_troy_oz / troy_oz_to_gram

    async def close(self) -> None:
        await self._client.aclose()
