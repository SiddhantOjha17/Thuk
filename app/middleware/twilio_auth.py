"""Twilio webhook authentication dependency."""

from fastapi import HTTPException, Request
from twilio.request_validator import RequestValidator

from app.config import get_settings


async def verify_twilio_signature(request: Request) -> None:
    """Verify that incoming requests are genuinely from Twilio.
    
    Uses Twilio's request validator. Raises HTTP 403 if invalid.
    """
    settings = get_settings()
    
    # If not configured, skip validation (e.g., local dev without ngrok)
    if not settings.twilio_auth_token or not settings.webhook_base_url:
        return
        
    validator = RequestValidator(settings.twilio_auth_token)
    
    # The URL Twilio used to make the request
    # Since we might be behind a reverse proxy (Render/Fly), we use the configured base_url
    url = f"{settings.webhook_base_url.rstrip('/')}/webhook/whatsapp"
    
    # Get form data and signature header
    form_data = await request.form()
    signature = request.headers.get("X-Twilio-Signature", "")
    
    if not validator.validate(url, dict(form_data), signature):
        raise HTTPException(
            status_code=403, 
            detail="Invalid Twilio signature"
        )
