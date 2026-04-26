import logging

import httpx

from elixir.shared.config import Settings

logger = logging.getLogger(__name__)

_BASE = "https://api.twelvedata.com"


class TwelveDataClient:
    def __init__(self, settings: Settings) -> None:
        self._api_key = settings.twelve_data_api_key
        self._client = httpx.AsyncClient(base_url=_BASE, timeout=15.0)

    async def get_price(self, symbol: str) -> float:
        resp = await self._client.get(
            "/price",
            params={"symbol": symbol, "apikey": self._api_key},
        )
        resp.raise_for_status()
        return float(resp.json()["price"])

    async def close(self) -> None:
        await self._client.aclose()
