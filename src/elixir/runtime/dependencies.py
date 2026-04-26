import uuid
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from elixir.runtime.context import RequestContext


async def get_db_session(request: Request):
    """Yields one AsyncSession per request, scoped to the request lifetime."""
    async with request.app.state.session_factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


async def get_request_context(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> RequestContext:
    """
    Assembles RequestContext from auth middleware state + the current db session.
    Raises 401 if the request was not authenticated or the session has been revoked.
    """
    user_id = getattr(request.state, "user_id", None)
    session_id = getattr(request.state, "session_id", None)

    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Check session is active and not revoked
    from elixir.domains.identity.repositories import IdentityRepository
    repo = IdentityRepository(db)
    session = await repo.get_session_by_id_and_user(user_id, session_id)
    if session is None or session.revoked_at is not None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session has been revoked or expired",
            headers={"WWW-Authenticate": "Bearer"},
        )

    request_id = getattr(request.state, "request_id", None) or str(uuid.uuid4())

    return RequestContext(
        user_id=user_id,
        session_id=session_id,
        request_id=request_id,
        db=db,
    )


# Type alias used throughout the API layer
RequestCtx = Annotated[RequestContext, Depends(get_request_context)]
