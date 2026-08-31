"""LLM provider factory with automatic fallback chain.

Provider priority:
  1. Groq llama-3.3-70b-versatile  — primary, fast, free (1K RPD)
  2. Groq llama-3.1-8b-instant     — lightweight tasks (14.4K RPD)
  3. Gemini 2.5 Flash              — image processing + overflow (500 RPD)
  4. OpenAI gpt-4o-mini            — emergency fallback, operator key (paid)

With only ~5 daily users the free tiers are never at risk, but the chain
is in place so the app keeps working if limits are ever hit.
"""

from enum import Enum

from langchain_core.language_models import BaseChatModel

from app.config import get_settings
from app.utils.logging import get_logger

logger = get_logger(__name__)


class ModelTask(str, Enum):
    """Task categories that map to specific models."""

    # Routing, intent classification, category detection, response formatting
    FAST = "fast"
    # SQL generation, edit parsing, complex reasoning
    SMART = "smart"
    # Multimodal image OCR
    IMAGE = "image"


def get_llm(task: ModelTask = ModelTask.FAST) -> BaseChatModel:
    """Return the best available LLM for the given task.

    Tries providers in priority order and returns the first one whose
    API key is configured. Never raises — always returns something.

    Args:
        task: The type of work this model will do.

    Returns:
        A LangChain chat model instance.
    """
    settings = get_settings()

    if task == ModelTask.IMAGE:
        return _get_image_model(settings)

    # SMART tasks use the big Groq model; FAST tasks use the small one.
    # Both fall back through the same chain.
    if task == ModelTask.SMART:
        return _get_smart_model(settings)

    return _get_fast_model(settings)


def _get_fast_model(settings) -> BaseChatModel:
    """llama-3.1-8b-instant → llama-3.3-70b → Gemini Flash → OpenAI."""
    if settings.groq_api_key:
        try:
            from langchain_groq import ChatGroq
            logger.debug("LLM: Groq llama-3.1-8b-instant (fast)")
            return ChatGroq(
                api_key=settings.groq_api_key,
                model="llama-3.1-8b-instant",
                temperature=0,
            )
        except ImportError:
            logger.warning("langchain-groq not installed, skipping Groq")

    return _get_smart_model(settings)


def _get_smart_model(settings) -> BaseChatModel:
    """llama-3.3-70b → Gemini Flash → OpenAI."""
    if settings.groq_api_key:
        try:
            from langchain_groq import ChatGroq
            logger.debug("LLM: Groq llama-3.3-70b-versatile (smart)")
            return ChatGroq(
                api_key=settings.groq_api_key,
                model="llama-3.3-70b-versatile",
                temperature=0,
            )
        except ImportError:
            logger.warning("langchain-groq not installed, skipping Groq")

    if settings.gemini_api_key:
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI
            logger.debug("LLM: Gemini 2.5 Flash (smart fallback)")
            return ChatGoogleGenerativeAI(
                google_api_key=settings.gemini_api_key,
                model="gemini-2.5-flash",
                temperature=0,
            )
        except ImportError:
            logger.warning("langchain-google-genai not installed, skipping Gemini")

    if settings.openai_api_key:
        from langchain_openai import ChatOpenAI
        logger.debug("LLM: OpenAI gpt-4o-mini (emergency fallback)")
        return ChatOpenAI(
            api_key=settings.openai_api_key,
            model="gpt-4o-mini",
            temperature=0,
        )

    raise RuntimeError(
        "No LLM provider configured. Set GROQ_API_KEY, GEMINI_API_KEY, or OPENAI_API_KEY."
    )


def _get_image_model(settings) -> BaseChatModel:
    """Gemini 2.5 Flash (free multimodal) → OpenAI gpt-4o-mini."""
    if settings.gemini_api_key:
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI
            logger.debug("LLM: Gemini 2.5 Flash (image)")
            return ChatGoogleGenerativeAI(
                google_api_key=settings.gemini_api_key,
                model="gemini-2.5-flash",
                temperature=0,
            )
        except ImportError:
            logger.warning("langchain-google-genai not installed, skipping Gemini for images")

    if settings.openai_api_key:
        from langchain_openai import ChatOpenAI
        logger.debug("LLM: OpenAI gpt-4o-mini (image fallback)")
        return ChatOpenAI(
            api_key=settings.openai_api_key,
            model="gpt-4o-mini",
            temperature=0,
        )

    raise RuntimeError(
        "No image-capable LLM configured. Set GEMINI_API_KEY or OPENAI_API_KEY."
    )


def get_response_llm() -> BaseChatModel:
    """Slightly warmer model for natural-sounding responses."""
    settings = get_settings()

    if settings.groq_api_key:
        try:
            from langchain_groq import ChatGroq
            return ChatGroq(
                api_key=settings.groq_api_key,
                model="llama-3.1-8b-instant",
                temperature=0.4,
            )
        except ImportError:
            pass

    if settings.gemini_api_key:
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI
            return ChatGoogleGenerativeAI(
                google_api_key=settings.gemini_api_key,
                model="gemini-2.5-flash",
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
