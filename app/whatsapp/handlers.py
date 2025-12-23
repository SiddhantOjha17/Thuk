"""WhatsApp webhook message handlers."""

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import crud
from app.database.schemas import WhatsAppMessage
from app.processors import ImageProcessor, VoiceProcessor
from app.utils.encryption import encrypt_api_key


async def parse_twilio_request(form_data: dict) -> WhatsAppMessage:
    """Parse incoming Twilio webhook request into WhatsAppMessage."""
    return WhatsAppMessage(
        from_number=form_data.get("From", "").replace("whatsapp:", ""),
        body=form_data.get("Body"),
        media_url=form_data.get("MediaUrl0"),
        media_content_type=form_data.get("MediaContentType0"),
        num_media=int(form_data.get("NumMedia", 0)),
    )


async def handle_incoming_message(
    message: WhatsAppMessage,
    db: AsyncSession,
) -> str:
    """Handle an incoming WhatsApp message.

    Returns the response message to send back.
    """
    # Get or create user
    user = await crud.get_user_by_phone(db, message.from_number)

    if user is None:
        # New user - create account
        user = await crud.create_user(db, message.from_number)
        return (
            "Welcome to Thuk - your expense tracker!\n\n"
            "To get started, please send me your OpenAI API key.\n"
            "Your key will be encrypted and stored securely.\n\n"
            "Get your key from: https://platform.openai.com/api-keys"
        )

    # Check if user has API key
    if user.openai_api_key_encrypted is None:
        # Check if this message is an API key
        body = (message.body or "").strip()
        if body.startswith("sk-"):
            # This looks like an API key
            encrypted_key = encrypt_api_key(body)
            await crud.update_user_api_key(db, user.id, encrypted_key)
            return (
                "API key saved successfully!\n\n"
                "You can now start tracking expenses. Try:\n"
                "- \"Spent 500 on food\"\n"
                "- \"Paid $20 for coffee\"\n"
                "- Send a screenshot of a bank transaction\n"
                "- Send a voice note describing your expense\n\n"
                "Type \"help\" for more commands!"
            )
        else:
            return (
                "Please send your OpenAI API key first.\n"
                "It should start with 'sk-'\n\n"
                "Get your key from: https://platform.openai.com/api-keys"
            )

    # User is set up - process the message
    return await process_user_message(message, user, db)


async def process_user_message(message: WhatsAppMessage, user, db: AsyncSession) -> str:
    """Process a message from a fully set up user."""
    # Check for media (image or voice)
    if message.num_media > 0 and message.media_url:
        content_type = message.media_content_type or ""

        if content_type.startswith("image/"):
            # Image processing (bank transaction screenshot)
            return await handle_image_message(message, user, db)
        elif content_type.startswith("audio/"):
            # Voice message
            return await handle_voice_message(message, user, db)

    # Text message - send to agent system
    from app.agents import process_message

    return await process_message(message.body or "", user, db)


async def handle_image_message(
    message: WhatsAppMessage, user, db: AsyncSession
) -> str:
    """Handle an image message (bank transaction screenshot)."""
    from app.config import get_settings
    
    settings = get_settings()
    
    try:
        # Download the image with Twilio auth (required for media URLs)
        auth = (settings.twilio_account_sid, settings.twilio_auth_token)
        async with httpx.AsyncClient(auth=auth) as client:
            response = await client.get(message.media_url)
            if response.status_code != 200:
                return f"Failed to download image (status {response.status_code}). Please try again."
            image_data = response.content

        if not image_data or len(image_data) < 100:
            return "Image appears to be empty. Please try sending again."

        # Process with vision API
        processor = ImageProcessor(user)
        extracted_text = await processor.extract_text(image_data)

        if not extracted_text:
            return "Couldn't extract any text from the image. Please try again with a clearer screenshot."

        # Parse the extracted text through the agent system
        from app.agents import process_message

        return await process_message(
            f"[From bank transaction screenshot]: {extracted_text}",
            user,
            db,
            source_type="image",
        )
    except Exception as e:
        print(f"Error processing image: {e}")
        return f"Error processing image: {str(e)}"


async def handle_voice_message(
    message: WhatsAppMessage, user, db: AsyncSession
) -> str:
    """Handle a voice message."""
    from app.config import get_settings
    
    settings = get_settings()
    
    try:
        # Download the audio with Twilio auth
        auth = (settings.twilio_account_sid, settings.twilio_auth_token)
        async with httpx.AsyncClient(auth=auth) as client:
            response = await client.get(message.media_url)
            if response.status_code != 200:
                return f"Failed to download voice message (status {response.status_code})."
            audio_data = response.content

        # Transcribe with Whisper
        processor = VoiceProcessor(user)
        transcribed_text = await processor.transcribe(audio_data)

        if not transcribed_text:
            return "Couldn't transcribe the voice message. Please try again or send a text message instead."

        # Process transcribed text through agent system
        from app.agents import process_message

        return await process_message(
            transcribed_text,
            user,
            db,
            source_type="voice",
        )
    except Exception as e:
        print(f"Error processing voice: {e}")
        return f"Error processing voice message: {str(e)}"


def get_help_message() -> str:
    """Get the help message."""
    return """*Thuk Commands*

*Add Expenses:*
- "Spent 500 on food"
- "Paid $20 for coffee yesterday"
- Send a bank transaction screenshot
- Send a voice note

*Split Payments:*
- "2000 dinner split with 4 people"
- "1000 movie with Rahul and Priya"
- "Who owes me money?"
- "Rahul paid me back"

*Query Expenses:*
- "How much did I spend today?"
- "Show this month's expenses"
- "Food expenses this week"

*Categories:*
- "Show my categories"
- "Add category Subscriptions"

*Other:*
- "Delete last expense"
- "Help" - Show this message
"""
