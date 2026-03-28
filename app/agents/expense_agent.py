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
    short_description: str | None = Field(
        None,
        description="A very short and clean description of the transaction (e.g. 'football turf', 'netflix', 'groceries'). This is optional."
    )


class ExpenseAgent:
    """Agent for managing expenses."""

    async def _detect_category_with_llm(
        self,
        user,
        description: str,
        available_categories: list[str],
        history: list[dict] | None = None,
    ) -> tuple[str | None, str | None]:
        """Use LLM to detect the best category for an expense description.

        Args:
            user: User model instance (for API key)
            description: The expense description (e.g., "sandwich", "uber to office")
            available_categories: List of available category names
            history: Conversation history for context

        Returns:
            Tuple of (category_name, short_description)
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
- If unsure or it could fit multiple, return null/None for the category.
- Also extract a concise `short_description` (1-3 words) directly describing the transaction (e.g., 'football turf', 'uber ride'). 
- Use the conversation history for context if the description is ambiguous.
- Your output should be purely categorical and descriptive.
"""

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
            short_desc = result.short_description

            if not detected:
                return None, short_desc

            # Validate it's one of the available categories
            for cat in available_categories:
                if cat.lower() == detected.lower():
                    return cat, short_desc

            return None, short_desc

        except Exception as e:
            from app.utils.logging import get_logger
            logger = get_logger(__name__)
            logger.error("LLM category detection failed", error=str(e))
            return None, None

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
        short_desc = parsed.description
        if category is None and parsed.description:
            # Get available categories for this user
            user_categories = await crud.get_user_categories(db, user.id)
            category_names = [c.name for c in user_categories]

            detected_category_name, extracted_desc = await self._detect_category_with_llm(
                user, parsed.description, category_names, history
            )
            
            if extracted_desc:
                short_desc = extracted_desc

            if detected_category_name:
                category = await crud.get_category_by_name(db, user.id, detected_category_name)
                if category:
                    category_source = "llm"

        # 3. Intercept if category is STILL None
        if category is None:
            # Save pending expense to Redis
            import json
            pending_data = {
                "amount": str(parsed.amount),
                "currency": parsed.currency,
                "description": short_desc,
                "expense_date": parsed.expense_date.isoformat() if parsed.expense_date else None,
                "source_type": source_type
            }
            await store.set_flag(user.phone_number, "pending_expense", json.dumps(pending_data), ttl=300)
            
            # Format categories for interactive reply
            user_categories = await crud.get_user_categories(db, user.id)
            cats_text = "\n".join([f"{i+1}. {c.name}" for i, c in enumerate(user_categories)])
            cats_text += f"\n{len(user_categories)+1}. Others"
            cats_text += "\n\n*(Tip: Or just type a new category name!)*"
            
            return f"I couldn't be sure about the category. What is this for?\n{cats_text}"

        # Create the expense
        expense = await crud.create_expense(
            db=db,
            user_id=user.id,
            amount=parsed.amount,
            currency=parsed.currency,
            description=short_desc, # Use the optionally refined short description
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
        instructions: str,
    ) -> str:
        """Edit the most recent expense using natural language instructions.

        Args:
            db: Database session
            user: User model instance
            instructions: Natural language instructions (e.g., 'shift it to groceries')

        Returns:
            Response message
        """
        from pydantic import BaseModel, Field
        from decimal import Decimal
        from langchain_openai import ChatOpenAI
        from langchain_core.messages import SystemMessage

        # Get last expense
        expenses = await crud.get_user_expenses(db, user.id, limit=1)
        if not expenses:
            return "No expenses found to edit."

        expense = expenses[0]

        class ExpensePatch(BaseModel):
            new_amount: float | None = Field(None, description="The updated numeric amount, if the user requested to change the amount.")
            new_description: str | None = Field(None, description="The updated description, if the user requested to change what it was for.")
            new_category_name: str | None = Field(None, description="The distinct new category name, if the user requested to shift/re-categorize it.")

        api_key = decrypt_api_key(user.openai_api_key_encrypted)
        llm = ChatOpenAI(
            api_key=api_key,
            model="gpt-4o-mini",
            temperature=0,
        ).with_structured_output(ExpensePatch)

        user_categories = await crud.get_user_categories(db, user.id)
        cat_str = ", ".join([c.name for c in user_categories])
        curr_cat = expense.category.name if expense.category else 'Others'

        prompt = f"""Apply this exact user instruction: '{instructions}' to the user's most recent expense object.
        
Current Amount: {expense.amount}
Current Description: {expense.description}
Current Category: {curr_cat}

Available Existing Categories: {cat_str}

RULES:
1. Return ONLY the fields that should mathematically or categorically change.
2. If changing the category, match carefully against the available lists. If it is entirely new, return the newly capitalized spelled category.
3. If an instruction says "shift this 278 expense to food", it means changing the category, NOT the amount or description.
"""
        try:
            patch: ExpensePatch = await llm.ainvoke([SystemMessage(content=prompt)])
        except Exception as e:
            return f"I couldn't process the edit instruction: {str(e)}"

        # Update fields dynamically
        changes = []
        if patch.new_amount is not None:
            expense.amount = Decimal(str(patch.new_amount))
            changes.append(f"amount to {patch.new_amount}")
            
        if patch.new_description is not None:
            expense.description = patch.new_description
            changes.append(f"description to '{patch.new_description}'")
            
        if patch.new_category_name is not None and patch.new_category_name.lower() != curr_cat.lower():
            if patch.new_category_name.lower() == "others":
                expense.category_id = None
                changes.append("category to Others")
            else:
                cat = await crud.get_category_by_name(db, user.id, patch.new_category_name)
                if not cat:
                    cat = await crud.create_category(db, user.id, patch.new_category_name)
                expense.category_id = cat.id
                changes.append(f"category to {cat.name}")

        if not changes:
            return "No specific modifications were understood from your message. Try being more direct (e.g. 'Make it 500 dollars')."

        await db.flush()

        # Format final
        amount_str = format_amount(expense.amount, expense.currency)
        return f"Updated expense: {amount_str}. (Changed {', '.join(changes)})"

    async def _resolve_category_reply(self, user, reply_text: str, categories: list[str]) -> str:
        """Use LLM to cleanly map a user's reply to a category or 'Others', handling typos."""
        try:
            from pydantic import BaseModel, Field
            class ResolutionResult(BaseModel):
                mapped_category: str = Field(description="The exact matched existing category, 'Others', or the brand new cleanly capitalized category name.")

            api_key = decrypt_api_key(user.openai_api_key_encrypted)
            llm = ChatOpenAI(
                api_key=api_key,
                model="gpt-4o-mini",
                temperature=0,
            ).with_structured_output(ResolutionResult)

            cat_str = ", ".join(categories)
            prompt = f"""The user is answering a prompt to select a category. 
Available existing categories: {cat_str}
Number mappings: 1 to N map to the list above in order, where N+1 maps to 'Others'.
User reply: '{reply_text}'

Task:
1. If the user replied with a number, map it correctly.
2. If they replied with text, check if it's a typo of an existing category. If so, return the EXACT existing category.
3. If they meant 'Others', return 'Others'.
4. If it's a completely new category (e.g. 'Gaming', 'Gym'), return the cleanly formatted, Capitalized new category name.
Only return the final string."""

            res = await llm.ainvoke([SystemMessage(content=prompt)])
            return res.mapped_category
        except Exception as e:
            from app.utils.logging import get_logger
            logger = get_logger(__name__)
            logger.error("LLM category resolution failed", error=str(e))
            return reply_text.strip().capitalize()

    async def resolve_pending(self, db: AsyncSession, user, reply_text: str) -> str:
        """Resolve a pending category assignment."""
        import json
        from decimal import Decimal
        from datetime import date
        
        pending_str = await store.get_flag(user.phone_number, "pending_expense")
        if not pending_str:
            return "No pending expense found or it expired."
            
        pending_data = json.loads(pending_str)
        user_categories = await crud.get_user_categories(db, user.id)
        cat_names = [c.name for c in user_categories]
        
        # Determine the target category
        mapped = await self._resolve_category_reply(user, reply_text, cat_names)
        
        category = None
        if mapped != "Others":
            category = await crud.get_category_by_name(db, user.id, mapped)
            if not category:
                # Create the new category!
                category = await crud.create_category(db, user.id, mapped)

        # Reconstruct parsed details
        exp_date_str = pending_data.get("expense_date")
        expense_date = date.fromisoformat(exp_date_str) if exp_date_str else date.today()

        # Create expense
        await crud.create_expense(
            db=db,
            user_id=user.id,
            amount=Decimal(pending_data["amount"]),
            currency=pending_data["currency"],
            description=pending_data.get("description"),
            category_id=category.id if category else None,
            source_type=SourceType(pending_data.get("source_type", "text")),
            expense_date=expense_date,
        )
        
        # Clear the flag
        await store.delete_flag(user.phone_number, "pending_expense")
        
        amount_str = format_amount(Decimal(pending_data["amount"]), pending_data["currency"])
        cat_str = f" ({category.name})" if category else " (Others)"
        return f"Added expense: {amount_str}{cat_str}"
