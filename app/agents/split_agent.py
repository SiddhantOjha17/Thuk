"""Split Agent - handles split payments and debt tracking."""

import uuid
from datetime import date
from decimal import Decimal, InvalidOperation

from sqlalchemy.ext.asyncio import AsyncSession

from app.database import crud
from app.database.models import DebtDirection, SourceType
from app.memory.redis_store import store
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

        total_amount = parsed.amount
        per_person = total_amount / Decimal(split_count)
        user_share = per_person
        others_owe = total_amount - user_share

        # Try to find matching category
        category = None
        if parsed.category_hint:
            category = await crud.get_category_by_name(db, user.id, parsed.category_hint)

        await crud.create_split_expense(
            db=db,
            user_id=user.id,
            amount=total_amount,
            currency=parsed.currency,
            description=parsed.description,
            category_id=category.id if category else None,
            source_type=SourceType(source_type),
            expense_date=parsed.expense_date or date.today(),
            split_count=split_count,
            split_people=parsed.split_people,
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

        if not summary["aggregated"]:
            return "You have no pending debts!"

        response = ["*Debt Summary*\n"]

        owes_me = [p for p in summary["aggregated"] if p["direction"] == DebtDirection.OWES_ME.value]
        i_owe = [p for p in summary["aggregated"] if p["direction"] != DebtDirection.OWES_ME.value]

        if owes_me:
            total_str = format_amount(summary["total_owed_to_me"], "INR")
            response.append(f"*People owe you* (total {total_str}):")
            for p in owes_me:
                count_label = f" ({p['count']} debts)" if p["count"] > 1 else ""
                response.append(f"  \u2022 {p['person_name']}: {format_amount(p['total'], p['currency'])}{count_label}")
            response.append("")

        if i_owe:
            total_str = format_amount(summary["total_i_owe"], "INR")
            response.append(f"*You owe* (total {total_str}):")
            for p in i_owe:
                count_label = f" ({p['count']} debts)" if p["count"] > 1 else ""
                response.append(f"  \u2022 {p['person_name']}: {format_amount(p['total'], p['currency'])}{count_label}")

        return "\n".join(response)

    async def settle_debt(
        self,
        db: AsyncSession,
        user,
        person_name: str,
        amount: Decimal | None = None,
    ) -> str:
        """Settle debts with a person — fully if no amount is given, otherwise
        applies a partial payment (asking which debt if the person has more
        than one unsettled one, rather than guessing an order).

        Args:
            db: Database session
            user: User model instance
            person_name: Name of the person
            amount: If given, a partial repayment amount instead of a full settle

        Returns:
            Response message
        """
        if amount is None:
            count = await crud.settle_debts_by_person(db, user.id, person_name)
            if count > 0:
                return f"Settled {count} debt(s) with {person_name}!"
            return f"No pending debts found with {person_name}."

        unsettled = await crud.get_unsettled_debts_by_person(db, user.id, person_name)

        if not unsettled:
            return f"No pending debts found with {person_name}."

        if len(unsettled) == 1:
            debt = await crud.apply_partial_payment(db, unsettled[0], amount)
            return self._payment_applied_message(person_name, amount, debt)

        # More than one debt with this person — don't guess which one it applies to.
        await store.set_flag(
            str(user.id),
            "pending_settle",
            {
                "person_name": person_name,
                "amount": str(amount),
                "currency": unsettled[0].currency,
                "debt_ids": [str(d.id) for d in unsettled],
            },
            ttl=120,
        )
        lines = [f"{person_name} has {len(unsettled)} separate debts. Which one is this payment for?\n"]
        for i, d in enumerate(unsettled, start=1):
            desc = f" ({d.related_expense.description})" if d.related_expense and d.related_expense.description else ""
            lines.append(f"{i}. {format_amount(d.amount, d.currency)}{desc}")
        lines.append("\nReply with a number.")
        return "\n".join(lines)

    async def resolve_pending_settle(self, db: AsyncSession, user, reply_text: str) -> str:
        """Resolve which debt a pending partial payment applies to."""
        pending = await store.get_flag(str(user.id), "pending_settle")
        if not pending:
            return "No pending payment found or it expired."

        try:
            choice = int(reply_text.strip())
        except ValueError:
            return "Please reply with just the number of the debt this payment is for."

        debt_ids = pending["debt_ids"]
        if not (1 <= choice <= len(debt_ids)):
            return f"Please reply with a number between 1 and {len(debt_ids)}."

        debt = await crud.get_debt_by_id(db, user.id, uuid.UUID(debt_ids[choice - 1]))
        await store.delete_flag(str(user.id), "pending_settle")

        if not debt:
            return "That debt no longer exists."

        try:
            amount = Decimal(pending["amount"])
        except (InvalidOperation, KeyError):
            return "Something went wrong reading that payment — please try again."

        debt = await crud.apply_partial_payment(db, debt, amount)
        return self._payment_applied_message(pending["person_name"], amount, debt)

    def _payment_applied_message(self, person_name: str, amount: Decimal, debt) -> str:
        amt_str = format_amount(amount, debt.currency)
        if debt.is_settled:
            return f"Recorded {amt_str} from {person_name} — that debt is now fully settled!"
        remaining_str = format_amount(debt.amount, debt.currency)
        return f"Recorded {amt_str} from {person_name}. Remaining: {remaining_str}."

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
