"""Analytics endpoints — summary and daily breakdown."""

from datetime import date, timedelta
from decimal import Decimal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.database.base import get_db
from app.database.models import Category, Expense, User
from app.database.schemas import AnalyticsDaily, AnalyticsSummary, CategoryAmount, DailyAmount

router = APIRouter()


def _default_range() -> tuple[date, date]:
    today = date.today()
    return today.replace(day=1), today


@router.get("/summary", response_model=AnalyticsSummary)
async def get_summary(
    start: date | None = Query(None),
    end: date | None = Query(None),
    currency: str = Query(default="INR"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Total spend + breakdown by category for a date range."""
    if not start or not end:
        start, end = _default_range()

    # Total + count
    total_q = await db.execute(
        select(func.sum(Expense.amount), func.count())
        .where(
            Expense.user_id == user.id,
            Expense.currency == currency,
            Expense.expense_date >= start,
            Expense.expense_date <= end,
        )
    )
    total_row = total_q.one()
    total = total_row[0] or Decimal("0")
    count = total_row[1]

    # By category
    cat_q = await db.execute(
        select(Category.name, Category.color, func.sum(Expense.amount))
        .outerjoin(Category, Expense.category_id == Category.id)
        .where(
            Expense.user_id == user.id,
            Expense.currency == currency,
            Expense.expense_date >= start,
            Expense.expense_date <= end,
        )
        .group_by(Category.name, Category.color)
        .order_by(func.sum(Expense.amount).desc())
    )
    by_category = [
        CategoryAmount(
            category_name=row[0] or "Other",
            amount=row[2],
            color=row[1] or "#9CA3AF",
        )
        for row in cat_q.all()
    ]

    return AnalyticsSummary(
        total=total,
        currency=currency,
        count=count,
        by_category=by_category,
        start_date=start,
        end_date=end,
    )


@router.get("/daily", response_model=AnalyticsDaily)
async def get_daily(
    start: date | None = Query(None),
    end: date | None = Query(None),
    currency: str = Query(default="INR"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Day-by-day spend totals — used for the area chart in Insights."""
    if not start or not end:
        start, end = _default_range()

    result = await db.execute(
        select(Expense.expense_date, func.sum(Expense.amount))
        .where(
            Expense.user_id == user.id,
            Expense.currency == currency,
            Expense.expense_date >= start,
            Expense.expense_date <= end,
        )
        .group_by(Expense.expense_date)
        .order_by(Expense.expense_date)
    )
    rows = {row[0]: row[1] for row in result.all()}

    # Fill in zero-spend days so charts render continuous lines
    days = []
    current = start
    while current <= end:
        days.append(DailyAmount(date=current, amount=rows.get(current, Decimal("0"))))
        current += timedelta(days=1)

    return AnalyticsDaily(currency=currency, days=days, start_date=start, end_date=end)
