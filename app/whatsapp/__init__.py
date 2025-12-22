"""WhatsApp integration package."""

from app.whatsapp.client import WhatsAppClient
from app.whatsapp.handlers import handle_incoming_message

__all__ = ["WhatsAppClient", "handle_incoming_message"]
