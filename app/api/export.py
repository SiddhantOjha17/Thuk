"""Export endpoint — streams CSV directly, no Redis temp link."""

import csv
import io

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.dependencies import get_current_user
from app.database.base import get_db
from app.database.models import Expense, User

router = APIRouter()


@router.get("/csv")
async def export_csv(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Stream all expenses as a CSV file."""
    result = await db.execute(
        select(Expense)
        .options(selectinload(Expense.category))
        .where(Expense.user_id == user.id)
        .order_by(Expense.expense_date.desc(), Expense.created_at.desc())
    )
    expenses = result.scalars().all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Date", "Amount", "Currency", "Description", "Category", "Source"])
    for exp in expenses:
        writer.writerow([
            exp.expense_date.isoformat(),
            str(exp.amount),
            exp.currency,
            exp.description or "",
            exp.category.name if exp.category else "Other",
            exp.source_type,
        ])

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=expenses.csv"},
    )
