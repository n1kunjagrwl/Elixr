import logging
from typing import Any

import httpx

from elixir.shared.config import Settings

logger = logging.getLogger(__name__)

_BASE = "https://eodhd.com/api"


class EodhdClient:
    def __init__(self, settings: Settings) -> None:
        self._api_key = settings.eodhd_api_key
        self._client = httpx.AsyncClient(base_url=_BASE, timeout=20.0)

    async def get_price(self, ticker: str, exchange: str = "NSE") -> float:
        resp = await self._client.get(
            f"/real-time/{ticker}.{exchange}",
            params={"api_token": self._api_key, "fmt": "json"},
        )
        resp.raise_for_status()
        return float(resp.json()["close"])

    async def close(self) -> None:
        await self._client.aclose()
