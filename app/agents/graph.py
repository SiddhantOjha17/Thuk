"""LangGraph workflow — main entry point for message processing."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.supervisor import SupervisorAgent, _agent_cache


async def process_message(
    message: str,
    user,
    db: AsyncSession,
    source_type: str = "text",
) -> str:
    """Process a user message through the agent system.

    Reuses a cached SupervisorAgent per user so the LangGraph workflow
    is only compiled once per user session instead of on every message.

    Args:
        message: The user's message text
        user: User model instance
        db: Database session
        source_type: Source of the message ("text", "image", "voice")

    Returns:
        Response message to send back to the user
    """
    user_key = str(user.id)
    supervisor = _agent_cache.get(user_key)
    if supervisor is None:
        supervisor = SupervisorAgent(user)
        _agent_cache[user_key] = supervisor

    return await supervisor.process(message, db, source_type)
