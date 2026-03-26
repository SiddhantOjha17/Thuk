"""Budget Agent - handles budget setting and checking."""

from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import Expense, User
from app.utils.currency import format_amount


class BudgetAgent:
    """Agent for managing monthly budgets."""

    async def set_budget(
        self, db: AsyncSession, user: User, amount: Decimal, currency: str = "INR"
    ) -> str:
        """Set the monthly budget for a user."""
        if not user.preferences:
            user.preferences = {}
            
        user.preferences["monthly_budget"] = {
            "amount": str(amount),
            "currency": currency,
        }
        
        # SQLAlchemy needs to know the JSON field changed
        from sqlalchemy.orm.attributes import flag_modified
        flag_modified(user, "preferences")
        
        await db.flush()
        
        amt_str = format_amount(amount, currency)
        return f"Monthly budget set to {amt_str}."

    async def get_budget_status(self, db: AsyncSession, user: User) -> str:
        """Get the current budget status for the month."""
        prefs = user.preferences or {}
        budget_dict = prefs.get("monthly_budget")
        
        if not budget_dict:
            return "You haven't set a monthly budget yet. Try 'set budget 5000'."
            
        budget_amount = Decimal(budget_dict["amount"])
        budget_currency = budget_dict.get("currency", "INR")
        
        spent = await self._get_current_month_spend(db, user.id, budget_currency)
        remaining = budget_amount - spent
        
        spent_str = format_amount(spent, budget_currency)
        budget_str = format_amount(budget_amount, budget_currency)
        
        if remaining < 0:
            rem_str = format_amount(abs(remaining), budget_currency)
            return f"*Budget Exceeded!*\nYou've spent {spent_str} out of your {budget_str} budget. You are over budget by {rem_str}."
        else:
            rem_str = format_amount(remaining, budget_currency)
            pct = (spent / budget_amount) * 100 if budget_amount > 0 else 0
            return f"*Budget Status*\nSpent: {spent_str} / {budget_str} ({pct:.1f}%)\nRemaining: {rem_str}"

    async def check_budget(self, db: AsyncSession, user: User) -> str | None:
        """Check budget and return a warning string if >80% spent."""
        prefs = user.preferences or {}
        budget_dict = prefs.get("monthly_budget")
        
        if not budget_dict:
            return None
            
        budget_amount = Decimal(budget_dict["amount"])
        budget_currency = budget_dict.get("currency", "INR")
        
        spent = await self._get_current_month_spend(db, user.id, budget_currency)
        
        if budget_amount == 0:
            return None
            
        pct = (spent / budget_amount) * 100
        
        if pct > 100:
            return f"⚠️ Warning: You've exceeded your monthly budget of {format_amount(budget_amount, budget_currency)}! (Spent: {format_amount(spent, budget_currency)})"
        elif pct >= 80:
            return f"⚠️ Warning: You've used {pct:.1f}% of your monthly budget."
            
        return None

    async def _get_current_month_spend(self, db: AsyncSession, user_id, currency: str) -> Decimal:
        """Calculate total spend for the current UTC month."""
        now = datetime.now(UTC)
        start_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0).date()
        
        stmt = (
            select(func.sum(Expense.amount))
            .where(Expense.user_id == user_id)
            .where(Expense.currency == currency)
            .where(Expense.expense_date >= start_of_month)
        )
        result = await db.execute(stmt)
        total = result.scalar()
        return total or Decimal("0.00")
