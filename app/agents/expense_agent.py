"""Expense Agent - handles adding, updating, and deleting expenses."""

from datetime import date
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.database import crud
from app.database.models import SourceType
from app.processors.text_parser import ParsedMessage
from app.utils.currency import format_amount


class ExpenseAgent:
    """Agent for managing expenses."""

    async def add_expense(
        self,
        db: AsyncSession,
        user,
        parsed: ParsedMessage,
        source_type: str = "text",
    ) -> str:
        """Add a new expense.

        Args:
            db: Database session
            user: User model instance
            parsed: Parsed message with extracted entities
            source_type: Source of the expense (text/image/voice)

        Returns:
            Response message
        """
        if parsed.amount is None:
            return "I couldn't detect an amount. Please try again with a clear amount like '500' or '$20'."

        # Try to find matching category
        category = None
        if parsed.category_hint:
            category = await crud.get_category_by_name(db, user.id, parsed.category_hint)

        # Create the expense
        expense = await crud.create_expense(
            db=db,
            user_id=user.id,
            amount=parsed.amount,
            currency=parsed.currency,
            description=parsed.description,
            category_id=category.id if category else None,
            source_type=SourceType(source_type),
            expense_date=parsed.expense_date or date.today(),
        )

        # Format response
        amount_str = format_amount(parsed.amount, parsed.currency)
        category_str = f" ({category.name})" if category else ""
        date_str = ""
        if parsed.expense_date and parsed.expense_date != date.today():
            date_str = f" on {parsed.expense_date.strftime('%b %d')}"

        return f"Added expense: {amount_str}{category_str}{date_str}"

    async def delete_last(self, db: AsyncSession, user) -> str:
        """Delete the most recent expense.

        Args:
            db: Database session
            user: User model instance

        Returns:
            Response message
        """
        expense = await crud.delete_last_expense(db, user.id)

        if expense:
            amount_str = format_amount(expense.amount, expense.currency)
            return f"Deleted last expense: {amount_str}"
        else:
            return "No expenses found to delete."

    async def edit_last(
        self,
        db: AsyncSession,
        user,
        new_amount: Decimal | None = None,
        new_description: str | None = None,
    ) -> str:
        """Edit the most recent expense.

        Args:
            db: Database session
            user: User model instance
            new_amount: New amount (optional)
            new_description: New description (optional)

        Returns:
            Response message
        """
        # Get last expense
        expenses = await crud.get_user_expenses(db, user.id, limit=1)
        if not expenses:
            return "No expenses found to edit."

        expense = expenses[0]

        # Update fields
        if new_amount is not None:
            expense.amount = new_amount
        if new_description is not None:
            expense.description = new_description

        await db.flush()

        amount_str = format_amount(expense.amount, expense.currency)
        return f"Updated expense to: {amount_str}"
