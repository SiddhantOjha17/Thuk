"""Image processor for extracting text from bank transaction screenshots."""

import base64
import json

from langchain_core.messages import HumanMessage, SystemMessage
from openai import AsyncOpenAI

from app.config import get_settings
from app.llm.factory import ModelTask, content_to_text, get_llm
from app.utils.logging import get_logger

logger = get_logger(__name__)

_EXTRACT_SYSTEM_PROMPT = """You are an expert at extracting transaction details from bank SMS screenshots and transaction receipts.

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
Be concise and include only the extracted information."""


class ImageProcessor:
    """Process images using Gemini vision (primary), OpenAI Vision as runtime fallback."""

    def __init__(self, user=None):
        """Initialize the OpenAI fallback client (Gemini is resolved lazily via the LLM factory)."""
        settings = get_settings()
        self._openai_client = AsyncOpenAI(api_key=settings.openai_api_key)

    async def extract_text(self, image_data: bytes) -> str | None:
        """Extract transaction details from a bank SMS/transaction screenshot.

        Tries Gemini (the documented primary provider) first, falling back to
        OpenAI Vision only if the Gemini call itself fails (auth/quota/network),
        so a single provider outage doesn't take the whole feature down.

        Args:
            image_data: Raw image bytes

        Returns:
            Extracted transaction details as text, or None if extraction failed
        """
        base64_image = base64.b64encode(image_data).decode("utf-8")

        try:
            llm = get_llm(ModelTask.IMAGE)
            response = await llm.ainvoke(
                [
                    SystemMessage(content=_EXTRACT_SYSTEM_PROMPT),
                    HumanMessage(
                        content=[
                            {
                                "type": "text",
                                "text": "Extract the transaction details from this image:",
                            },
                            {
                                "type": "image_url",
                                "image_url": f"data:image/jpeg;base64,{base64_image}",
                            },
                        ]
                    ),
                ]
            )
            result = content_to_text(response.content).strip()
            if result and "NO_TRANSACTION_FOUND" not in result:
                return result
            return None
        except Exception as e:
            logger.warning(
                "Gemini image extraction failed, falling back to OpenAI Vision",
                error=str(e),
            )

        try:
            response = await self._openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": _EXTRACT_SYSTEM_PROMPT},
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
            logger.error(
                "Error extracting text from image (Gemini and OpenAI both failed)",
                error=str(e),
                exc_info=True,
            )
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
            response = await self._openai_client.chat.completions.create(
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
