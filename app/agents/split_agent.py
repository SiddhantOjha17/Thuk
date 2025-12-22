"""Split Agent - handles split payments and debt tracking."""

from datetime import date
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.database import crud
from app.database.models import DebtDirection, SourceType
from app.processors.text_parser import ParsedMessage
from app.utils.currency import format_amount


class SplitAgent:
    """Agent for managing split payments and debts."""

    async def create_split_expense(
        self,
        db: AsyncSession,
        user,
        parsed: ParsedMessage,
        source_type: str = "text",
    ) -> str:
        """Create an expense with split payment tracking.

        Args:
            db: Database session
            user: User model instance
            parsed: Parsed message with split information
            source_type: Source of the expense (text/image/voice)

        Returns:
            Response message
        """
        if parsed.amount is None:
            return "I couldn't detect an amount. Please specify how much was spent."

        if parsed.split_count is None and parsed.split_people is None:
            return "Please specify how many people to split with or name them."

        # Determine split count
        split_count = parsed.split_count
        if split_count is None and parsed.split_people:
            split_count = len(parsed.split_people) + 1  # +1 for the user

        # Calculate amounts
        total_amount = parsed.amount
        per_person = total_amount / Decimal(split_count)
        user_share = per_person
        others_owe = total_amount - user_share

        # Try to find matching category
        category = None
        if parsed.category_hint:
            category = await crud.get_category_by_name(db, user.id, parsed.category_hint)

        # Create the expense (user's share only)
        expense = await crud.create_expense(
            db=db,
            user_id=user.id,
            amount=user_share,  # Only user's share is their expense
            currency=parsed.currency,
            description=parsed.description,
            category_id=category.id if category else None,
            source_type=SourceType(source_type),
            expense_date=parsed.expense_date or date.today(),
            metadata={
                "original_amount": str(total_amount),
                "split_count": split_count,
            },
        )

        # Create split record
        await crud.create_split(
            db=db,
            expense_id=expense.id,
            user_id=user.id,
            total_people=split_count,
            user_paid=total_amount,  # User paid the full amount
            total_amount=total_amount,
        )

        # Create debts for named people
        if parsed.split_people:
            for person_name in parsed.split_people:
                await crud.create_debt(
                    db=db,
                    user_id=user.id,
                    person_name=person_name,
                    amount=per_person,
                    currency=parsed.currency,
                    direction=DebtDirection.OWES_ME,
                    related_expense_id=expense.id,
                )

        # Format response
        total_str = format_amount(total_amount, parsed.currency)
        share_str = format_amount(user_share, parsed.currency)
        others_str = format_amount(others_owe, parsed.currency)

        response = ["Split expense created!"]
        response.append(f"Total: {total_str}")
        response.append(f"Your share: {share_str}")
        response.append(f"Others owe you: {others_str} ({split_count - 1} people)")

        if parsed.split_people:
            per_person_str = format_amount(per_person, parsed.currency)
            response.append("\n*Debts created:*")
            for person in parsed.split_people:
                response.append(f"- {person}: {per_person_str}")

        return "\n".join(response)

    async def get_debt_summary(self, db: AsyncSession, user) -> str:
        """Get summary of all debts.

        Args:
            db: Database session
            user: User model instance

        Returns:
            Formatted debt summary
        """
        summary = await crud.get_debt_summary(db, user.id)

        if not summary["debts"]:
            return "You have no pending debts!"

        response = ["*Debt Summary*\n"]

        # Group by direction
        owes_me = []
        i_owe = []

        for debt in summary["debts"]:
            debt_str = f"- {debt.person_name}: {format_amount(debt.amount, debt.currency)}"
            if debt.direction == DebtDirection.OWES_ME.value:
                owes_me.append(debt_str)
            else:
                i_owe.append(debt_str)

        if owes_me:
            total_owed = format_amount(summary["total_owed_to_me"], "INR")
            response.append(f"*People owe you:* {total_owed}")
            response.extend(owes_me)
            response.append("")

        if i_owe:
            total_i_owe = format_amount(summary["total_i_owe"], "INR")
            response.append(f"*You owe:* {total_i_owe}")
            response.extend(i_owe)

        return "\n".join(response)

    async def settle_debt(
        self,
        db: AsyncSession,
        user,
        person_name: str,
    ) -> str:
        """Mark debts with a person as settled.

        Args:
            db: Database session
            user: User model instance
            person_name: Name of the person

        Returns:
            Response message
        """
        count = await crud.settle_debts_by_person(db, user.id, person_name)

        if count > 0:
            return f"Settled {count} debt(s) with {person_name}!"
        else:
            return f"No pending debts found with {person_name}."

    async def add_debt(
        self,
        db: AsyncSession,
        user,
        person_name: str,
        amount: Decimal,
        currency: str,
        direction: DebtDirection,
    ) -> str:
        """Add a standalone debt (not from a split).

        Args:
            db: Database session
            user: User model instance
            person_name: Name of the person
            amount: Debt amount
            currency: Currency code
            direction: Who owes whom

        Returns:
            Response message
        """
        await crud.create_debt(
            db=db,
            user_id=user.id,
            person_name=person_name,
            amount=amount,
            currency=currency,
            direction=direction,
        )

        amount_str = format_amount(amount, currency)
        if direction == DebtDirection.OWES_ME:
            return f"Added: {person_name} owes you {amount_str}"
        else:
            return f"Added: You owe {person_name} {amount_str}"
