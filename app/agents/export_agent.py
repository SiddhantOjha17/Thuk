"""Export Agent - handles the chat 'export' command."""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import Expense, User


class ExportAgent:
    """Agent for the chat 'export' command."""

    async def export_and_get_url(self, db: AsyncSession, user: User) -> str:
        """Point the user at the in-app CSV export.

        The iOS app already has a working authenticated CSV export (Wallet tab,
        `APIClient.requestRawData("/api/export/csv")`), which hands the file
        straight to the native share sheet. There's no equivalent for chat to
        hand back a file, so the best this can do is direct the user there —
        a previous version of this generated a temporary public download link
        left over from the WhatsApp/Twilio-era bot, but no route ever served
        that link in the FastAPI app, so it 404'd for every user.
        """
        count = await db.scalar(
            select(func.count()).select_from(Expense).where(Expense.user_id == user.id)
        )
        if not count:
            return "You don't have any expenses to export yet."

        return "Head to the Wallet tab and tap Export to download your expenses as a CSV."
