"""FastAPI application - main entry point."""

from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Form, Request
from fastapi.responses import PlainTextResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database.base import get_db
from app.database.schemas import WhatsAppMessage
from app.memory.redis_store import store
from app.middleware.twilio_auth import verify_twilio_signature
from app.middleware.rate_limit import check_rate_limit
from app.utils.logging import setup_logging, get_logger
from app.whatsapp.client import get_whatsapp_client
from app.whatsapp.handlers import handle_incoming_message, parse_twilio_request

settings = get_settings()
logger = get_logger(__name__)


settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    # Startup
    setup_logging(debug=settings.debug)
    logger.info("Thuk is starting up...")
    yield
    # Shutdown
    logger.info("Thuk is shutting down...")


app = FastAPI(
    title="Thuk - WhatsApp Expense Tracker",
    description="Multi-agent WhatsApp bot for tracking expenses",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/")
async def root():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "Thuk WhatsApp Expense Tracker",
        "version": "0.1.0",
    }


@app.get("/health")
async def health_check(db: AsyncSession = Depends(get_db)):
    """Health check for deployment platforms."""
    try:
        # Test DB connection
        await db.execute(text("SELECT 1"))
        return {"status": "ok", "db": "ok"}
    except Exception as e:
        logger.error("Health check failed", error=str(e))
        from fastapi import HTTPException
        raise HTTPException(status_code=503, detail={"status": "error", "db": "failed"})


@app.post("/webhook/whatsapp", dependencies=[Depends(verify_twilio_signature), Depends(check_rate_limit)])
async def whatsapp_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Handle incoming WhatsApp messages from Twilio.

    Twilio sends form-encoded data, which we parse into our schema.
    """
    # Parse form data
    form_data = await request.form()
    form_dict = dict(form_data)

    # Parse into our message schema
    message = await parse_twilio_request(form_dict)

    # Process the message
    response_text = await handle_incoming_message(message, db)

    # Send response back via Twilio
    try:
        whatsapp_client = get_whatsapp_client()
        await whatsapp_client.send_message(
            to=f"whatsapp:{message.from_number}",
            body=response_text,
        )
    except Exception as e:
        logger.error("Error sending WhatsApp message", error=str(e), to=message.from_number)

    # Return TwiML response (empty is fine for async)
    return PlainTextResponse(
        content="<?xml version='1.0' encoding='UTF-8'?><Response></Response>",
        media_type="application/xml",
    )


@app.get("/webhook/whatsapp")
async def whatsapp_webhook_verify(request: Request):
    """Handle Twilio webhook verification (if needed)."""
    return PlainTextResponse(content="OK")


@app.get("/export/{export_id}/expenses.csv")
async def download_export(export_id: str):
    """Download an exported CSV file."""
    redis = await store.get_client()
    key = f"thuk:export:{export_id}"
    csv_content = await redis.get(key)
    
    if not csv_content:
        return PlainTextResponse("Export not found or expired.", status_code=404)
        
    return PlainTextResponse(
        content=csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=expenses.csv"}
    )


# Development endpoint for testing without WhatsApp
@app.post("/api/test/message")
async def test_message(
    phone_number: str = Form(...),
    message: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    """Test endpoint for sending messages without WhatsApp.

    Useful for development and testing.
    """
    test_message = WhatsAppMessage(
        from_number=phone_number,
        body=message,
    )

    response = await handle_incoming_message(test_message, db)

    return {
        "status": "success",
        "input": message,
        "response": response,
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
    )
