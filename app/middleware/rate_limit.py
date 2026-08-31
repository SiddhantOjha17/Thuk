"""Rate limiting dependency for API endpoints."""

from fastapi import Depends, HTTPException, Request, status

from app.auth.dependencies import get_current_user
from app.database.models import User
from app.memory.redis_store import store


async def check_rate_limit(
    request: Request,
    user: User = Depends(get_current_user),
) -> None:
    """Limit each authenticated user to 60 requests per minute.

    Uses the user's UUID so it works regardless of IP or token rotation.
    """
    allowed = await store.check_rate_limit(
        str(user.id), max_requests=60, window_secs=60
    )
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many requests. Please slow down.",
        )
