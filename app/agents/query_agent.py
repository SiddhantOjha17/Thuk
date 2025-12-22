"""Query Agent - handles expense queries and analytics."""

from datetime import date, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.database import crud
from app.processors.text_parser import ParsedMessage
from app.utils.currency import format_amount


class QueryAgent:
    """Agent for querying and analyzing expenses."""

    def _get_date_range(self, time_range: str | None) -> tuple[date, date]:
        """Convert time range string to date range."""
        today = date.today()

        if time_range == "today":
            return today, today
        elif time_range == "yesterday":
            yesterday = today - timedelta(days=1)
            return yesterday, yesterday
        elif time_range == "this_week":
            start = today - timedelta(days=today.weekday())
            return start, today
        elif time_range == "last_week":
            end = today - timedelta(days=today.weekday() + 1)
            start = end - timedelta(days=6)
            return start, end
        elif time_range == "this_month":
            start = today.replace(day=1)
            return start, today
        elif time_range == "last_month":
            first_this_month = today.replace(day=1)
            end = first_this_month - timedelta(days=1)
            start = end.replace(day=1)
            return start, end
        else:
            # Default to this month
            return today.replace(day=1), today

    async def get_summary(
        self,
        db: AsyncSession,
        user,
        parsed: ParsedMessage,
    ) -> str:
        """Get expense summary for a time period.

        Args:
            db: Database session
            user: User model instance
            parsed: Parsed message with query parameters

        Returns:
            Formatted summary message
        """
        start_date, end_date = self._get_date_range(parsed.time_range)

        # Get category filter if specified
        category_id = None
        if parsed.category_hint:
            category = await crud.get_category_by_name(db, user.id, parsed.category_hint)
            if category:
                category_id = category.id

        # Get summary
        summary = await crud.get_expense_summary(
            db=db,
            user_id=user.id,
            start_date=start_date,
            end_date=end_date,
            currency=parsed.currency,
        )

        if summary["count"] == 0:
            time_str = self._format_time_range(parsed.time_range)
            return f"No expenses found {time_str}."

        # Format response
        total_str = format_amount(summary["total_amount"], summary["currency"])
        time_str = self._format_time_range(parsed.time_range)

        response = [f"*Spending Summary* {time_str}\n"]
        response.append(f"Total: {total_str} ({summary['count']} expenses)\n")

        if summary["by_category"]:
            response.append("\n*By Category:*")
            for cat_name, amount in sorted(
                summary["by_category"].items(),
                key=lambda x: x[1],
                reverse=True,
            ):
                cat_str = format_amount(amount, summary["currency"])
                response.append(f"- {cat_name}: {cat_str}")

        return "\n".join(response)

    async def list_expenses(
        self,
        db: AsyncSession,
        user,
        parsed: ParsedMessage,
        limit: int = 10,
    ) -> str:
        """List recent expenses.

        Args:
            db: Database session
            user: User model instance
            parsed: Parsed message with query parameters
            limit: Maximum number of expenses to return

        Returns:
            Formatted list of expenses
        """
        start_date, end_date = self._get_date_range(parsed.time_range)

        # Get category filter if specified
        category_id = None
        if parsed.category_hint:
            category = await crud.get_category_by_name(db, user.id, parsed.category_hint)
            if category:
                category_id = category.id

        expenses = await crud.get_user_expenses(
            db=db,
            user_id=user.id,
            start_date=start_date,
            end_date=end_date,
            category_id=category_id,
            currency=parsed.currency,
            limit=limit,
        )

        if not expenses:
            time_str = self._format_time_range(parsed.time_range)
            return f"No expenses found {time_str}."

        time_str = self._format_time_range(parsed.time_range)
        response = [f"*Recent Expenses* {time_str}\n"]

        for exp in expenses:
            amount_str = format_amount(exp.amount, exp.currency)
            cat_str = f" ({exp.category.name})" if exp.category else ""
            desc_str = f" - {exp.description}" if exp.description else ""
            date_str = exp.expense_date.strftime("%b %d")
            response.append(f"- {date_str}: {amount_str}{cat_str}{desc_str}")

        return "\n".join(response)

    def _format_time_range(self, time_range: str | None) -> str:
        """Format time range for display."""
        mapping = {
            "today": "today",
            "yesterday": "yesterday",
            "this_week": "this week",
            "last_week": "last week",
            "this_month": "this month",
            "last_month": "last month",
        }
        return mapping.get(time_range, "this month")
