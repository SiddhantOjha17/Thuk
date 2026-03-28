"""LLM-based intent classifier for robust natural language parsing."""

from datetime import date
from typing import Any

from langchain_core.messages import SystemMessage, HumanMessage
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from app.processors.text_parser import Intent, ParsedMessage
from app.utils.encryption import decrypt_api_key
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

    def __init__(self, user):
        """Initialize with user's specific API key."""
        self.user = user
        api_key = decrypt_api_key(user.openai_api_key_encrypted)
        # We use a cheap, fast model for intent routing
        self.llm = ChatOpenAI(
            api_key=api_key,
            model="gpt-4o-mini",
            temperature=0,
        ).with_structured_output(IntentClassificationResult)

    async def classify(self, text: str, history: list[dict[str, Any]] | None = None) -> ParsedMessage:
        """Classify the intent using an LLM.
        
        Args:
            text: The user's message text
            history: Optional conversation history for context
            
        Returns:
            ParsedMessage with all extracted fields
        """
        today = date.today().isoformat()
        system_prompt = f"""You are Thuk's Intent Classification Engine.
Your singular job is to read the latest user message, consider the conversational memory if relevant, and extract the precise intent along with any underlying parameters. Do NOT guess.

Current Date: {today}

RULES:
1. Identify the logical Intent from the allowed enum.
2. Rely heavily on the provided conversation history to understand context for short replies (like "yes", "shift it", "delete").
3. If a user is giving an instruction that is totally ambiguous or lacks crucial parameters for its intent, classify as `CLARIFY` and provide a friendly `clarification_question`.

SUPPORTED INTENTS:
- ADD_EXPENSE: A new transaction or purchase.
- QUERY_EXPENSES: Asking for summaries, lists, analytics, or comparisons.
- EDIT_EXPENSE: Modifying a previously entered expense. (Extract `edit_instructions`).
- SPLIT_PAYMENT: Dividing an expense among people.
- CHECK_DEBTS: Checking who owes them money.
- SETTLE_DEBT: Marking a balance as paid off.
- ADD_CATEGORY: Creating a brand new organizational category. (Extract `extracted_category_name`).
- LIST_CATEGORIES: Viewing existing categories.
- DELETE_EXPENSE: Erasing an expense.
- SET_BUDGET: Setting a spending limit.
- CHECK_BUDGET: Viewing current limits vs spending.
- EXPORT_EXPENSES: Creating a CSV or data export.
- HELP: Asking for commands or assistance.
- CLARIFY: Use ONLY when perfectly ambiguous and cannot be securely deduced from context.
- UNKNOWN: Nonsense input completely unrelated to personal finance.

Do your best to infer parameters strictly from the natural text provided."""

        messages = [SystemMessage(content=system_prompt)]
        
        if history:
            transcript = []
            for msg in history:
                role = "User" if msg["role"] == "user" else "Assistant"
                transcript.append(f"{role}: {msg['content']}")
            
            transcript_str = "\n".join(transcript)
            messages.append(SystemMessage(content=f"--- CONVERSATIONAL MEMORY ---\n{transcript_str}\n--- END MEMORY ---"))

        messages.append(HumanMessage(content=text))

        try:
            result: IntentClassificationResult = await self.llm.ainvoke(messages)
            
            # Map the structured output to our internal ParsedMessage dataclass
            return ParsedMessage(
                intent=result.intent,
                amount=Decimal(str(result.amount)) if result.amount is not None else None,
                currency=result.currency,
                description=result.description,
                category_hint=None, # LLM doesn't do category_hint here, it's done by CategoryAgent
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
            # Safe fallback
            return ParsedMessage(intent=Intent.UNKNOWN, raw_text=text)
