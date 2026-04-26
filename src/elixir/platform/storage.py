import os
from pathlib import Path

from elixir.shared.config import Settings


class LocalStorage:
    def __init__(self, base_path: str) -> None:
        self._base = Path(base_path)
        self._base.mkdir(parents=True, exist_ok=True)

    def user_path(self, user_id: str) -> Path:
        p = self._base / user_id
        p.mkdir(parents=True, exist_ok=True)
        return p

    async def save(self, user_id: str, filename: str, data: bytes) -> str:
        dest = self.user_path(user_id) / filename
        dest.write_bytes(data)
        return str(dest)

    async def read(self, path: str) -> bytes:
        return Path(path).read_bytes()

    async def delete(self, path: str) -> None:
        p = Path(path)
        if p.exists():
            p.unlink()


def build_storage_client(settings: Settings) -> LocalStorage:
    return LocalStorage(settings.storage_base_path)
