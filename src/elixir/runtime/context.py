from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession


@dataclass
class RequestContext:
    """
    Per-request ambient state. Assembled once by get_request_context() Depends
    and passed through the service call chain. Never stored globally.
    """

    user_id: UUID
    session_id: UUID | None
    request_id: str
    db: AsyncSession
