"""LLM provider factory with automatic fallback chain.

Provider priority:
  1. Gemini gemini-3.6-flash  — primary, free, structured output supported
  2. OpenAI gpt-4o-mini        — fallback, paid (minimal cost)

Groq's current free models (compound-mini, compound) do not support
tool calling / structured output which we require, so they are not used.
"""

from langchain_core.language_models import BaseChatModel

from app.config import get_settings
from app.utils.logging import get_logger

logger = get_logger(__name__)


class ModelTask:
    FAST  = "fast"   # intent classification, category detection, formatting
    SMART = "smart"  # SQL generation, edit parsing
    IMAGE = "image"  # multimodal image OCR


def get_llm(task: str = ModelTask.FAST) -> BaseChatModel:
    """Return the best available LLM for the given task."""
    settings = get_settings()

    if settings.gemini_api_key:
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI
            logger.debug("LLM: Gemini gemini-3.6-flash", task=task)
            return ChatGoogleGenerativeAI(
                google_api_key=settings.gemini_api_key,
                model="gemini-3.6-flash",
                temperature=0,
            )
        except ImportError:
            logger.warning("langchain-google-genai not installed")

    if settings.openai_api_key:
        from langchain_openai import ChatOpenAI
        logger.debug("LLM: OpenAI gpt-4o-mini (fallback)", task=task)
        return ChatOpenAI(
            api_key=settings.openai_api_key,
            model="gpt-4o-mini",
            temperature=0,
        )

    raise RuntimeError(
        "No LLM provider configured. Set GEMINI_API_KEY or OPENAI_API_KEY."
    )


def get_response_llm() -> BaseChatModel:
    """Slightly warmer model for natural-sounding query responses."""
    settings = get_settings()

    if settings.gemini_api_key:
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI
            return ChatGoogleGenerativeAI(
                google_api_key=settings.gemini_api_key,
                model="gemini-3.6-flash",
                temperature=0.4,
            )
        except ImportError:
            pass

    from langchain_openai import ChatOpenAI
    return ChatOpenAI(
        api_key=settings.openai_api_key,
        model="gpt-4o-mini",
        temperature=0.7,
    )
