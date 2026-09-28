"""Recurring Agent - handles setting up, listing, and stopping recurring expenses."""

from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.database import crud
from app.database.crud import VALID_CADENCES
from app.utils.currency import format_amount


class RecurringAgent:
    """Agent for managing recurring expenses (rent, subscriptions, EMIs)."""

    async def add_recurring(
        self,
        db: AsyncSession,
        user,
        amount: Decimal | None,
        currency: str,
        description: str | None,
        cadence: str | None,
    ) -> str:
        """Set up a new recurring expense."""
        if amount is None:
            return "I couldn't detect an amount. Try 'add netflix 500 monthly'."
        if not description:
            return "What's this recurring expense for? Try 'add netflix 500 monthly'."

        cadence = (cadence or "monthly").lower()
        if cadence not in VALID_CADENCES:
            cadence = "monthly"

        recurring = await crud.create_recurring_expense(
            db=db,
            user_id=user.id,
            amount=amount,
            currency=currency,
            description=description,
            cadence=cadence,
        )

        amt_str = format_amount(amount, currency)
        return (
            f"Got it — {amt_str} for '{recurring.description}' will be added "
            f"{cadence}, starting today."
        )

    async def list_recurring(self, db: AsyncSession, user) -> str:
        """List a user's active recurring expenses."""
        items = await crud.get_user_recurring_expenses(db, user.id)
        if not items:
            return "You don't have any recurring expenses set up. Try 'add rent 15000 monthly'."

        lines = ["*Recurring expenses*\n"]
        for r in items:
            amt_str = format_amount(r.amount, r.currency)
            lines.append(f"- {r.description}: {amt_str} ({r.cadence}, next on {r.next_run_date.isoformat()})")
        return "\n".join(lines)

    async def stop_recurring(self, db: AsyncSession, user, name_hint: str | None) -> str:
        """Stop a recurring expense by fuzzy-matching its description."""
        if not name_hint:
            return "Which recurring expense should I stop? Try 'stop netflix'."

        matches = await crud.find_recurring_expenses_by_description(db, user.id, name_hint)

        if not matches:
            return f"I couldn't find a recurring expense matching '{name_hint}'."
        if len(matches) > 1:
            names = ", ".join(m.description for m in matches)
            return f"Found more than one match: {names}. Be more specific."

        await crud.deactivate_recurring_expense(db, matches[0].id)
        return f"Stopped recurring expense: {matches[0].description}."
