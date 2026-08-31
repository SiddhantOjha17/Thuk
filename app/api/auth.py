"""Auth endpoints — register, login, refresh."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.service import (
    create_access_token,
    generate_refresh_token,
    hash_password,
    hash_refresh_token,
    refresh_token_expiry,
    verify_password,
)
from app.database import crud
from app.database.base import get_db
from app.database.schemas import LoginRequest, RefreshRequest, RegisterRequest, TokenResponse
from app.utils.logging import get_logger

router = APIRouter()
logger = get_logger(__name__)


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(body: RegisterRequest, db: AsyncSession = Depends(get_db)):
    """Create a new account and return tokens."""
    existing = await crud.get_user_by_email(db, body.email)
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    user = await crud.create_user(
        db,
        name=body.name,
        email=body.email,
        password_hash=hash_password(body.password),
    )

    raw_refresh, refresh_hash = generate_refresh_token()
    await crud.store_refresh_token(db, user.id, refresh_hash, refresh_token_expiry())

    logger.info("User registered", user_id=str(user.id))
    return TokenResponse(
        access_token=create_access_token(user.id),
        refresh_token=raw_refresh,
    )


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    """Authenticate and return tokens."""
    user = await crud.get_user_by_email(db, body.email)
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    raw_refresh, refresh_hash = generate_refresh_token()
    await crud.store_refresh_token(db, user.id, refresh_hash, refresh_token_expiry())

    return TokenResponse(
        access_token=create_access_token(user.id),
        refresh_token=raw_refresh,
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh(body: RefreshRequest, db: AsyncSession = Depends(get_db)):
    """Exchange a valid refresh token for a new access token."""
    token_hash = hash_refresh_token(body.refresh_token)
    stored = await crud.get_refresh_token(db, token_hash)

    if not stored:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )

    # Rotate: revoke old, issue new
    await crud.revoke_refresh_token(db, token_hash)
    raw_refresh, new_hash = generate_refresh_token()
    await crud.store_refresh_token(db, stored.user_id, new_hash, refresh_token_expiry())

    return TokenResponse(
        access_token=create_access_token(stored.user_id),
        refresh_token=raw_refresh,
    )
