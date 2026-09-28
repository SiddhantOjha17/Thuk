"""FastAPI application — main entry point."""

from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import router as api_router
from app.config import get_settings
from app.database.base import get_db
from app.utils.logging import get_logger, setup_logging

settings = get_settings()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging(debug=settings.debug)
    logger.info("Thuk starting up")
    yield
    logger.info("Thuk shutting down")


app = FastAPI(
    title="Thuk API",
    description="Personal expense tracker — mobile API",
    version="1.0.0",
    lifespan=lifespan,
)

# The only clients are the native iOS app and share extension, which use Bearer-token
# auth and are never subject to browser CORS enforcement — no origin needs to be allowed.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)


@app.get("/")
async def root():
    return {"status": "ok", "service": "Thuk API", "version": "1.0.0"}


@app.get("/health")
async def health(db: AsyncSession = Depends(get_db)):
    try:
        await db.execute(text("SELECT 1"))
        return {"status": "ok", "db": "ok"}
    except Exception as e:
        logger.error("Health check failed", error=str(e))
        from fastapi import HTTPException
        raise HTTPException(status_code=503, detail="Database unavailable")
