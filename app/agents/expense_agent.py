"""Expense Agent - handles adding, updating, and deleting expenses."""

from datetime import date
from decimal import Decimal

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import crud
from app.database.models import SourceType
from app.memory.redis_store import store
from app.processors.text_parser import ParsedMessage
from app.utils.currency import format_amount
from app.utils.encryption import decrypt_api_key

class CategoryDetectionResult(BaseModel):
    """Structured output for category detection."""
    category_name: str | None = Field(
        None, 
        description="The best matching category name from the allowed list, or None if it should be 'Other'."
    )


class ExpenseAgent:
    """Agent for managing expenses."""

    async def _detect_category_with_llm(
        self,
        user,
        description: str,
        available_categories: list[str],
        history: list[dict] | None = None,
    ) -> str | None:
        """Use LLM to detect the best category for an expense description.

        Args:
            user: User model instance (for API key)
            description: The expense description (e.g., "sandwich", "uber to office")
            available_categories: List of available category names
            history: Conversation history for context

        Returns:
            Best matching category name, or None if unsure
        """
        if not description or not available_categories:
            return None

        try:
            api_key = decrypt_api_key(user.openai_api_key_encrypted)
            llm = ChatOpenAI(
                api_key=api_key,
                model="gpt-4o-mini",
                temperature=0,
            ).with_structured_output(CategoryDetectionResult)

            categories_str = ", ".join(available_categories)
            system_prompt = f"""Categorize this expense into one of these exact categories: {categories_str}

Rules:
- If the expense clearly fits a category, return that category name exactly as listed.
- If unsure or it could fit multiple, return null/None.
- Use the conversation history for context if the description is ambiguous.
- Common examples:
  - "sandwich", "pizza", "dinner" -> Food
  - "uber", "metro", "parking" -> Transport
  - "netflix", "movie" -> Entertainment
  - "amazon", "clothes" -> Shopping"""

            messages = [SystemMessage(content=system_prompt)]
            
            if history:
                for msg in history:
                    if msg["role"] == "user":
                        messages.append(HumanMessage(content=msg["content"]))
                    else:
                        messages.append(AIMessage(content=msg["content"]))
                        
            messages.append(HumanMessage(content=f"Expense description: {description}"))

            result: CategoryDetectionResult = await llm.ainvoke(messages)
            detected = result.category_name

            if not detected:
                return None

            # Validate it's one of the available categories
            for cat in available_categories:
                if cat.lower() == detected.lower():
                    return cat

            return None

        except Exception as e:
            print(f"LLM category detection failed: {e}")
            return None

    async def add_expense(
        self,
        db: AsyncSession,
        user,
        parsed: ParsedMessage,
        source_type: str = "text",
        history: list[dict] | None = None,
    ) -> str:
        """Add a new expense.

        Args:
            db: Database session
            user: User model instance
            parsed: Parsed message with extracted entities
            source_type: Source of the expense (text/image/voice)
            history: Conversation history context

        Returns:
            Response message
        """
        if parsed.amount is None:
            return "I couldn't detect an amount. Please try again with a clear amount like '500' or '$20'."

        # Try to find matching category
        category = None
        category_source = None

        # 1. First try keyword-based category hint
        if parsed.category_hint:
            category = await crud.get_category_by_name(db, user.id, parsed.category_hint)
            if category:
                category_source = "keyword"

        # 2. If no category found, use LLM to detect
        if category is None and parsed.description:
            # Get available categories for this user
            user_categories = await crud.get_user_categories(db, user.id)
            category_names = [c.name for c in user_categories]

            detected_category_name = await self._detect_category_with_llm(
                user, parsed.description, category_names, history
            )

            if detected_category_name:
                category = await crud.get_category_by_name(db, user.id, detected_category_name)
                if category:
                    category_source = "llm"

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
        """Delete the most recent expense with confirmation.

        Args:
            db: Database session
            user: User model instance

        Returns:
            Response message
        """
        # Check if already confirmed
        is_pending = await store.get_flag(user.phone_number, "pending_delete")
        
        if not is_pending:
            # First step: get the latest expense and ask for confirmation
            expenses = await crud.get_user_expenses(db, user.id, limit=1)
            if not expenses:
                return "No expenses found to delete."
                
            expense = expenses[0]
            amount_str = format_amount(expense.amount, expense.currency)
            desc_str = f" for '{expense.description}'" if expense.description else ""
            
            # Set flag for 60 seconds
            await store.set_flag(user.phone_number, "pending_delete", True, ttl=60)
            
            return f"Are you sure you want to delete the expense of {amount_str}{desc_str}? Reply 'yes' to confirm."

        # Second step: actually delete
        await store.delete_flag(user.phone_number, "pending_delete")
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
