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
        system_prompt = f"""You are Thuk's Intent Classification Engine. Your job is to classify user messages for a personal expense tracker.

Current Date: {today}

CRITICAL RULE: When in doubt, assume ADD_EXPENSE. Users message this bot to track spending. Short messages like "297 groceries", "500 food", "paid 100 for lunch" are ALWAYS ADD_EXPENSE. Never ask for clarification on something that is clearly an expense.

ROUTING RULES:
- If there is ANY amount + ANY item/place/person mentioned → ADD_EXPENSE
- If it asks "how much", "show", "summary", "spent" as a question → QUERY_EXPENSES  
- If it mentions "split" or "divide" or "among" → SPLIT_PAYMENT
- If it mentions editing/changing/correcting a past entry → EDIT_EXPENSE
- If it asks "who owes" or "debts" → CHECK_DEBTS
- If it says someone "paid back" → SETTLE_DEBT
- If it asks to "add a category" → ADD_CATEGORY
- If it asks to "show categories" → LIST_CATEGORIES
- If it asks to delete → DELETE_EXPENSE
- If it mentions setting/checking a budget → SET_BUDGET / CHECK_BUDGET
- If it says export/download/CSV → EXPORT_EXPENSES
- If it asks for help or commands → HELP
- CLARIFY: Use ONLY when there is NO amount whatsoever and intent is completely unclear
- UNKNOWN: ONLY for messages clearly unrelated to money/expenses (greetings with no context, random text)

SUPPORTED INTENTS: ADD_EXPENSE, QUERY_EXPENSES, EDIT_EXPENSE, SPLIT_PAYMENT, CHECK_DEBTS, SETTLE_DEBT, ADD_CATEGORY, LIST_CATEGORIES, DELETE_EXPENSE, SET_BUDGET, CHECK_BUDGET, EXPORT_EXPENSES, HELP, CLARIFY, UNKNOWN

IMPORTANT: If a message comes from a bank screenshot or payment app (e.g. starts with "From bank transaction"), treat the extracted amount and merchant as an ADD_EXPENSE. Extract the amount and merchant name as the description.

Use conversation history to understand context for replies like "yes", "delete that", "change it"."""

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
