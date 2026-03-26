"""Rate limiting dependency for webhooks."""

from fastapi import Depends, HTTPException, Request

from app.memory.redis_store import store


async def check_rate_limit(request: Request) -> None:
    """Check if the phone number has exceeded the rate limit.
    
    Extracts phone number from Twilio form data.
    """
    form_data = await request.form()
    phone_number = form_data.get("From", "").replace("whatsapp:", "")
    
    if not phone_number:
        return  # Can't rate limit without a phone number
        
    # Limit: 20 requests per 60 seconds
    is_allowed = await store.check_rate_limit(phone_number, max_requests=20, window_secs=60)
    
    if not is_allowed:
        # We don't raise HTTPException because Twilio will just retry 429s or error out.
        # Instead, we just drop the request or send a quick XML response back
        # But for FastAPI dependency, raising HTTPException is standard. Let's do that,
        # or we can attach it to the request and let the handler decide.
        # Given the requirements, a HTTP 429 is appropriate. 
        raise HTTPException(
            status_code=429,
            detail="Too many requests. Please wait a minute before sending more messages."
        )
