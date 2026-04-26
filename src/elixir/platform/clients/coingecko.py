import logging
from typing import Any

import httpx

from elixir.shared.config import Settings

logger = logging.getLogger(__name__)

_BASE = "https://api.coingecko.com/api/v3"


class CoinGeckoClient:
    def __init__(self, settings: Settings) -> None:
        headers = {}
        if settings.coingecko_api_key:
            headers["x-cg-demo-api-key"] = settings.coingecko_api_key
        self._client = httpx.AsyncClient(base_url=_BASE, headers=headers, timeout=15.0)

    async def get_price(self, coin_id: str, vs_currency: str = "inr") -> float:
        resp = await self._client.get(
            "/simple/price",
            params={"ids": coin_id, "vs_currencies": vs_currency},
        )
        resp.raise_for_status()
        data = resp.json()
        return data[coin_id][vs_currency]

    async def close(self) -> None:
        await self._client.aclose()
