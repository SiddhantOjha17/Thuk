"""Voice processor for transcribing voice messages."""

import io
import os
import tempfile

from openai import AsyncOpenAI

from app.config import get_settings
from app.utils.logging import get_logger

logger = get_logger(__name__)


class VoiceProcessor:
    """Process voice messages using OpenAI Whisper API."""

    def __init__(self, user=None):
        """Initialize using the operator OpenAI key (used for Whisper)."""
        settings = get_settings()
        self.client = AsyncOpenAI(api_key=settings.openai_api_key)

    async def transcribe(self, audio_data: bytes) -> str | None:
        """Transcribe a voice message to text.

        Args:
            audio_data: Raw audio bytes (typically OGG format from WhatsApp)

        Returns:
            Transcribed text, or None if transcription failed
        """
        tmp_path = None
        try:
            # WhatsApp sends voice notes as OGG/Opus — save to temp file for Whisper API
            with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp:
                tmp.write(audio_data)
                tmp_path = tmp.name

            with open(tmp_path, "rb") as audio_file:
                response = await self.client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file,
                    # No language= so Whisper auto-detects: supports Hindi, Hinglish, Tamil, etc.
                    prompt="This is a voice message about expenses, money, and transactions. Amounts may be in rupees, dollars, or other currencies.",
                )

            return response.text if response.text else None

        except Exception as e:
            logger.error("Error transcribing audio", error=str(e), exc_info=True)
            return None
        finally:
            if tmp_path and os.path.exists(tmp_path):
                os.unlink(tmp_path)

    async def transcribe_from_buffer(self, audio_buffer: io.BytesIO) -> str | None:
        """Transcribe from a BytesIO buffer.

        Args:
            audio_buffer: Audio data as BytesIO

        Returns:
            Transcribed text, or None if transcription failed
        """
        return await self.transcribe(audio_buffer.read())
