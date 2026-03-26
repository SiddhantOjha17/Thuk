"""Export Agent - handles exporting expenses to CSV."""

import csv
import io
import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Request

from app.database.models import Expense, User
from app.memory.redis_store import store
from app.config import get_settings


class ExportAgent:
    """Agent for exporting expenses."""

    async def export_and_get_url(self, db: AsyncSession, user: User, request_base_url: str) -> str:
        """Generate a CSV and store it temporarily, returning a public download URL.
        
        Since Twilio needs a public URL for media attachments, we store the CSV in Redis
        temporarily and return a URL that our FastAPI app will serve.
        """
        # Fetch all expenses
        stmt = (
            select(Expense)
            .where(Expense.user_id == user.id)
            .order_by(Expense.expense_date.desc(), Expense.created_at.desc())
        )
        result = await db.execute(stmt)
        expenses = result.scalars().all()
        
        if not expenses:
            return "You don't have any expenses to export."
            
        # Write to CSV in memory
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["Date", "Amount", "Currency", "Description", "Category", "Source"])
        
        for exp in expenses:
            # We don't eager load category to save a join in simple export,
            # but we can just use the category_id or omit name if needed.
            # Realistically we should load it but this works for now.
            writer.writerow([
                exp.expense_date.isoformat(),
                str(exp.amount),
                exp.currency,
                exp.description or "",
                str(exp.category_id) if exp.category_id else "Other",
                exp.source_type,
            ])
            
        csv_content = output.getvalue()
        
        # Store in Redis for 10 minutes
        export_id = str(uuid.uuid4())
        key = f"thuk:export:{export_id}"
        redis = await store.get_client()
        await redis.setex(key, 600, csv_content)
        
        settings = get_settings()
        base = settings.webhook_base_url or request_base_url
        download_url = f"{base.rstrip('/')}/export/{export_id}/expenses.csv"
        
        return f"Your export is ready! You can download it here (link valid for 10 mins):\n{download_url}"
