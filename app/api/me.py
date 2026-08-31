"""Current user profile endpoint."""

from fastapi import APIRouter, Depends

from app.auth.dependencies import get_current_user
from app.database.models import User
from app.database.schemas import UserResponse

router = APIRouter()


@router.get("/api/me", response_model=UserResponse)
async def get_me(user: User = Depends(get_current_user)):
    """Return the authenticated user's profile."""
    return user
