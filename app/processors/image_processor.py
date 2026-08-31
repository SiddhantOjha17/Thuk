"""Image processor for extracting text from bank transaction screenshots."""

import base64
import json

from openai import AsyncOpenAI

from app.config import get_settings
from app.utils.logging import get_logger

logger = get_logger(__name__)


class ImageProcessor:
    """Process images using OpenAI Vision API."""

    def __init__(self, user=None):
        """Initialize using the operator LLM (Gemini for images, OpenAI fallback)."""
        # ImageProcessor still uses OpenAI vision as a direct client;
        # Gemini vision is used via the LLMFactory in the agent layer.
        settings = get_settings()
        self.client = AsyncOpenAI(api_key=settings.openai_api_key)

    async def extract_text(self, image_data: bytes) -> str | None:
        """Extract transaction details from a bank SMS/transaction screenshot.

        Args:
            image_data: Raw image bytes

        Returns:
            Extracted transaction details as text, or None if extraction failed
        """
        # Encode image to base64
        base64_image = base64.b64encode(image_data).decode("utf-8")

        try:
            response = await self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": """You are an expert at extracting transaction details from bank SMS screenshots and transaction receipts.
                        
Extract the following information if present:
- Amount (with currency symbol if visible)
- Merchant/Description (who the payment was to)
- Date (if visible)
- Transaction type (debit/credit)
- Account details (masked, if visible)

Format your response as a natural language description like:
"Paid ₹500 to Swiggy on Dec 20"
or
"Received $100 from John on Dec 19"

If you cannot extract any transaction details, respond with "NO_TRANSACTION_FOUND".
Be concise and include only the extracted information.""",
                    },
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": "Extract the transaction details from this image:",
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{base64_image}",
                                    "detail": "high",
                                },
                            },
                        ],
                    },
                ],
                max_tokens=200,
            )

            result = response.choices[0].message.content
            if result and "NO_TRANSACTION_FOUND" not in result:
                return result
            return None

        except Exception as e:
            logger.error("Error extracting text from image", error=str(e), exc_info=True)
            return None

    async def analyze_receipt(self, image_data: bytes) -> dict | None:
        """Analyze a receipt image for detailed item breakdown.

        Args:
            image_data: Raw image bytes

        Returns:
            Dictionary with receipt details, or None if analysis failed
        """
        base64_image = base64.b64encode(image_data).decode("utf-8")

        try:
            response = await self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": """Extract receipt details as JSON:
{
    "total": <number>,
    "currency": "<3-letter code>",
    "merchant": "<store name>",
    "date": "<YYYY-MM-DD or null>",
    "items": [{"name": "<item>", "amount": <number>}]
}
Return only valid JSON.""",
                    },
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "Extract receipt details:"},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{base64_image}",
                                },
                            },
                        ],
                    },
                ],
                max_tokens=500,
            )

            result = response.choices[0].message.content
            if result:
                # Try to parse as JSON
                try:
                    return json.loads(result)
                except json.JSONDecodeError:
                    return None
            return None

        except Exception as e:
            logger.error("Error analyzing receipt", error=str(e), exc_info=True)
            return None
