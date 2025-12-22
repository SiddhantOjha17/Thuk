"""LangGraph workflow - main entry point for message processing."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.supervisor import SupervisorAgent


async def process_message(
    message: str,
    user,
    db: AsyncSession,
    source_type: str = "text",
) -> str:
    """Process a user message through the agent system.

    This is the main entry point for the multi-agent system.

    Args:
        message: The user's message text
        user: User model instance
        db: Database session
        source_type: Source of the message ("text", "image", "voice")

    Returns:
        Response message to send back to the user
    """
    supervisor = SupervisorAgent(user)
    return await supervisor.process(message, db, source_type)
