import logging
from typing import Any

import httpx

from elixir.shared.config import Settings

logger = logging.getLogger(__name__)

_AMFI_URL = "https://api.mfapi.in/mf"


class AMFIClient:
    def __init__(self, settings: Settings) -> None:
        self._client = httpx.AsyncClient(timeout=30.0)

    async def get_nav(self, scheme_code: str) -> dict[str, Any]:
        resp = await self._client.get(f"{_AMFI_URL}/{scheme_code}")
        resp.raise_for_status()
        return resp.json()

    async def close(self) -> None:
        await self._client.aclose()
