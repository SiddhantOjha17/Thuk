"""LLM-based intent classifier for robust natural language parsing."""

from datetime import date
from decimal import Decimal
from typing import Any

from langchain_core.messages import SystemMessage, HumanMessage
from pydantic import BaseModel, Field

from app.llm.factory import get_llm, ModelTask
from app.processors.text_parser import Intent, ParsedMessage
from app.utils.logging import get_logger

logger = get_logger(__name__)


class IntentClassificationResult(BaseModel):
    """Structured output from the LLM classifier."""
    
    intent: Intent = Field(
        description="The primary intent of the user's message. Use UNKNOWN if it doesn't match any supported intent."
    )
    amount: float | None = Field(
        None, description="The monetary amount mentioned, if any."
    )
    currency: str = Field(
        "INR", description="The currency code (e.g., INR, USD, EUR). Default is INR."
    )
    description: str | None = Field(
        None, description="A short description of the expense or category."
    )
    expense_date: date | None = Field(
        None, description="The date the expense occurred, if mentioned in the past. ISO format YYYY-MM-DD."
    )
    split_count: int | None = Field(
        None, description="Number of people to split the expense with (including the user). Used for SPLIT_PAYMENT."
    )
    split_people: list[str] | None = Field(
        None, description="A list of names of people involved in a split payment (e.g., ['Alice', 'Bob'])."
    )
    person_name: str | None = Field(
        None, description="The name of the person involved in a debt or split. Used for SETTLE_DEBT or CHECK_DEBTS."
    )
    time_range: str | None = Field(
        None, description="Time range for queries (e.g. 'today', 'yesterday', 'this_week', 'last_week', 'this_month', 'last_month')."
    )
    extracted_category_name: str | None = Field(
        None, description="If the user asks to ADD a new category (e.g., 'create category Gym'), extract 'Gym' here."
    )
    edit_instructions: str | None = Field(
        None, description="If the user is asking to EDIT an expense, transcribe their specific edit instructions clearly (e.g., 'Shift it from shopping to groceries')."
    )
    clarification_question: str | None = Field(
        None, description="If the intent strongly requires CLARIFY, what exact question should we ask the user?"
    )


class IntentClassifier:
    """Uses LLM to robustly classify intents from natural language."""

    def __init__(self):
        """Initialize using the operator-level LLM factory."""
        from app.llm.factory import get_llm, ModelTask
        # Fast 8B model is plenty for intent routing
        self.llm = get_llm(ModelTask.FAST).with_structured_output(IntentClassificationResult)

    async def classify(self, text: str, history: list[dict[str, Any]] | None = None) -> ParsedMessage:
        """Classify the intent using an LLM.

        Args:
            text: The user's message text
            history: Optional conversation history for context

        Returns:
            ParsedMessage with all extracted fields
        """
        from app.utils.currency import parse_amount, detect_currency

        today = date.today().isoformat()

        # Pre-extract amount with the fast regex utility and pass it as a hint
        # so the LLM doesn't have to guess numeric values from text
        pre_amount = parse_amount(text)
        pre_currency = detect_currency(text)
        hint = ""
        if pre_amount is not None:
            hint = f"\n\nPRE-EXTRACTED HINT: The message appears to contain amount {pre_amount} {pre_currency}. Use this if it matches context."

        # Cap input length to prevent runaway prompts
        safe_text = text[:1500]

        system_prompt = f"""You are Thuk's Intent Classification Engine for a WhatsApp expense tracker.

Current Date: {today}

CRITICAL DEFAULT RULE: When in doubt, classify as ADD_EXPENSE. Users open this bot to log spending.
Short messages like "297 groceries", "500 food", "paid 100 for lunch", "chai 30" are ALWAYS ADD_EXPENSE.
Do NOT ask for clarification on anything that looks like a spend.

HINGLISH & NATURAL LANGUAGE SUPPORT — these are all ADD_EXPENSE:
- "500 ka khana" (500 for food)
- "aaj 200 auto mein gaya" (today 200 spent on auto)
- "bhai 1200 diye dinner ke liye" (gave 1200 for dinner)
- "five hundred rupees for coffee" (written-out number, amount=500)
- "spent two thousand on groceries" (amount=2000)

ROUTING RULES:
- amount + item/place/person → ADD_EXPENSE
- "split", "divide", "among", "between X and Y" with amount → SPLIT_PAYMENT
- "how much", "show", "what did I spend", "summary" (as question) → QUERY_EXPENSES
- "change", "edit", "update", "actually make it", "correct" referring to a past expense → EDIT_EXPENSE
- "who owes", "debts", "owes me" → CHECK_DEBTS
- "[name] paid me back", "settled", "received from" → SETTLE_DEBT
- "add category [name]" → ADD_CATEGORY
- "delete", "remove", "undo" → DELETE_EXPENSE
- "set budget [amount]" → SET_BUDGET
- "check budget", "budget status" → CHECK_BUDGET
- "export", "download", "CSV" → EXPORT_EXPENSES
- "help" → HELP
- CLARIFY: ONLY if there is truly NO amount and intent is completely unclear
- UNKNOWN: ONLY for obvious non-expense chatter (e.g. "What's the weather?")

CONTEXTUAL REPLIES — use conversation history:
- "yes" after "are you sure you want to delete?" → DELETE_EXPENSE
- "no" / "cancel" after any confirmation → UNKNOWN (let it fall through gracefully)
- "actually make it 600" after adding an expense → EDIT_EXPENSE
- A number like "3" or a word like "food" after a category-selection prompt → RESOLVE_CATEGORY

FOR BANK SCREENSHOTS (message starts with "[From bank transaction screenshot]"):
- Always ADD_EXPENSE. Extract the merchant/description and amount.

FOR AMOUNTS:
- Parse written numbers: "five hundred" → 500, "two thousand" → 2000
- k-suffix already handled: use the PRE-EXTRACTED HINT if present
- Default currency: INR

SUPPORTED INTENTS: ADD_EXPENSE, QUERY_EXPENSES, EDIT_EXPENSE, SPLIT_PAYMENT, CHECK_DEBTS,
SETTLE_DEBT, ADD_CATEGORY, LIST_CATEGORIES, DELETE_EXPENSE, SET_BUDGET, CHECK_BUDGET,
EXPORT_EXPENSES, RESOLVE_CATEGORY, HELP, CLARIFY, UNKNOWN"""

        messages = [SystemMessage(content=system_prompt)]

        if history:
            transcript = "\n".join(
                f"{'User' if m['role'] == 'user' else 'Assistant'}: {m['content']}"
                for m in history
            )
            messages.append(SystemMessage(content=f"--- CONVERSATION HISTORY ---\n{transcript}\n--- END HISTORY ---"))

        messages.append(HumanMessage(content=safe_text + hint))

        try:
            result: IntentClassificationResult = await self.llm.ainvoke(messages)

            # Prefer LLM-extracted amount; fall back to pre-extracted regex amount
            llm_amount = Decimal(str(result.amount)) if result.amount is not None else None
            final_amount = llm_amount if llm_amount is not None else pre_amount
            final_currency = result.currency if result.currency else pre_currency

            return ParsedMessage(
                intent=result.intent,
                amount=final_amount,
                currency=final_currency,
                description=result.description,
                category_hint=None,
                expense_date=result.expense_date,
                split_count=result.split_count,
                split_people=result.split_people,
                person_name=result.person_name,
                time_range=result.time_range,
                extracted_category_name=result.extracted_category_name,
                edit_instructions=result.edit_instructions,
                raw_text=result.clarification_question if result.intent == Intent.CLARIFY else text,
            )
        except Exception as e:
            logger.error("LLM intent classification failed", error=str(e), exc_info=True)
            return ParsedMessage(intent=Intent.UNKNOWN, raw_text=text)
