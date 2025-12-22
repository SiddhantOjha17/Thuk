"""Voice processor for transcribing voice messages."""

import io
import tempfile

from openai import AsyncOpenAI

from app.utils.encryption import decrypt_api_key


class VoiceProcessor:
    """Process voice messages using OpenAI Whisper API."""

    def __init__(self, user):
        """Initialize with user's API key."""
        self.user = user
        api_key = decrypt_api_key(user.openai_api_key_encrypted)
        self.client = AsyncOpenAI(api_key=api_key)

    async def transcribe(self, audio_data: bytes) -> str | None:
        """Transcribe a voice message to text.

        Args:
            audio_data: Raw audio bytes (typically OGG format from WhatsApp)

        Returns:
            Transcribed text, or None if transcription failed
        """
        try:
            # WhatsApp sends voice notes as OGG/Opus
            # Save to temp file for API
            with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp:
                tmp.write(audio_data)
                tmp_path = tmp.name

            # Open the file for the API
            with open(tmp_path, "rb") as audio_file:
                response = await self.client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file,
                    language="en",  # Can be auto-detected, but specifying helps
                    prompt="This is a voice message about expenses, money, and transactions. The user might mention amounts in rupees, dollars, or other currencies.",
                )

            # Clean up temp file
            import os
            os.unlink(tmp_path)

            return response.text if response.text else None

        except Exception as e:
            print(f"Error transcribing audio: {e}")
            return None

    async def transcribe_from_buffer(self, audio_buffer: io.BytesIO) -> str | None:
        """Transcribe from a BytesIO buffer.

        Args:
            audio_buffer: Audio data as BytesIO

        Returns:
            Transcribed text, or None if transcription failed
        """
        return await self.transcribe(audio_buffer.read())
