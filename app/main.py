"""FastAPI application - main entry point."""

from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Form, Request
from fastapi.responses import PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database.base import get_db
from app.database.schemas import WhatsAppMessage
from app.whatsapp.client import get_whatsapp_client
from app.whatsapp.handlers import handle_incoming_message, parse_twilio_request


settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    # Startup
    print("Thuk is starting up...")
    yield
    # Shutdown
    print("Thuk is shutting down...")


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
async def health_check():
    """Health check for deployment platforms."""
    return {"status": "ok"}


@app.post("/webhook/whatsapp")
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
        print(f"Error sending WhatsApp message: {e}")

    # Return TwiML response (empty is fine for async)
    return PlainTextResponse(
        content="<?xml version='1.0' encoding='UTF-8'?><Response></Response>",
        media_type="application/xml",
    )


@app.get("/webhook/whatsapp")
async def whatsapp_webhook_verify(request: Request):
    """Handle Twilio webhook verification (if needed)."""
    return PlainTextResponse(content="OK")


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
