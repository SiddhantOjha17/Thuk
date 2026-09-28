"""Authentication utilities."""

from app.auth import service
from app.auth.dependencies import get_current_user

__all__ = ["get_current_user", "service"]
