"""Twilio WhatsApp client for sending messages."""

from twilio.rest import Client

from app.config import get_settings


class WhatsAppClient:
    """Client for sending WhatsApp messages via Twilio."""

    def __init__(self):
        """Initialize Twilio client."""
        self.settings = get_settings()
        self.client = Client(
            self.settings.twilio_account_sid,
            self.settings.twilio_auth_token,
        )
        self.from_number = self.settings.twilio_whatsapp_number

    async def send_message(self, to: str, body: str) -> str:
        """Send a WhatsApp message.

        Args:
            to: The recipient phone number (with whatsapp: prefix)
            body: The message body

        Returns:
            The message SID
        """
        # Ensure the to number has whatsapp: prefix
        if not to.startswith("whatsapp:"):
            to = f"whatsapp:{to}"

        message = self.client.messages.create(
            body=body,
            from_=self.from_number,
            to=to,
        )
        return message.sid

    async def send_template_message(
        self, to: str, template_id: str, variables: dict | None = None
    ) -> str:
        """Send a template message (for first contact).

        Note: Twilio sandbox doesn't require templates, but production does.
        """
        # For now, just send regular message
        # In production, you'd use template messages
        return await self.send_message(to, str(variables or {}))


# Singleton instance
_client: WhatsAppClient | None = None


def get_whatsapp_client() -> WhatsAppClient:
    """Get or create WhatsApp client singleton."""
    global _client
    if _client is None:
        _client = WhatsAppClient()
    return _client
