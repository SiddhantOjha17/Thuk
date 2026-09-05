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


def content_to_text(content) -> str:
    """Flatten a LangChain message's `.content` into plain text.

    Gemini (via langchain-google-genai) returns content as a list of blocks
    (e.g. [{"type": "text", "text": "...", "extras": {...}}]) rather than a
    plain string — every raw `.content` read needs to go through this instead
    of assuming a string.
    """
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = [
            block.get("text", "")
            for block in content
            if isinstance(block, dict) and block.get("type") == "text"
        ]
        return "".join(parts)
    return str(content)


def get_llm(task: str = ModelTask.FAST) -> BaseChatModel:
    """Return the best available LLM for the given task."""
    settings = get_settings()

    if settings.gemini_api_key:
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI
            # gemini-3.6-flash defaults to reasoning_effort="medium" (a "thinking"
            # mode) when unset, which adds ~25s of latency per call for tasks
            # that are plain classification/extraction and need no multi-step
            # reasoning. SMART (SQL generation) keeps a bit more headroom than
            # FAST/IMAGE since it has to reason about schema/joins.
            effort = "low" if task == ModelTask.SMART else "minimal"
            logger.debug("LLM: Gemini gemini-3.6-flash", task=task, reasoning_effort=effort)
            return ChatGoogleGenerativeAI(
                google_api_key=settings.gemini_api_key,
                model="gemini-3.6-flash",
                temperature=0,
                reasoning_effort=effort,
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
                reasoning_effort="minimal",
            )
        except ImportError:
            pass

    from langchain_openai import ChatOpenAI
    return ChatOpenAI(
        api_key=settings.openai_api_key,
        model="gpt-4o-mini",
        temperature=0.7,
    )
