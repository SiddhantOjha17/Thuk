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
    person_name: str | None = Field(
        None, description="The name of the person involved in a debt or split. Used for SETTLE_DEBT or CHECK_DEBTS."
    )
    time_range: str | None = Field(
        None, description="Time range for queries (e.g. 'today', 'yesterday', 'this_week', 'last_week', 'this_month', 'last_month')."
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
        
        system_prompt = f"""You are an expert natural language classification system for an expense tracker bot.
Your job is to read the user's message (and conversation history) and extract the precise intent and entities.

IMPORTANT INSTRUCTION: We only support English requests. Extract the intent and details accurately.
Today's date is {today}. If the user refers to "yesterday", "last week", calculate the date relative to today or use the time_range enum.

Supported Intents:
- ADD_EXPENSE: Adding a new expense (e.g., "spent 500 on food", "paid for cab 20")
- QUERY_EXPENSES: Asking for a summary or list (e.g., "how much did I spend this week?", "show my expenses")
- SPLIT_PAYMENT: Splitting an expense (e.g., "split 1000 with 3 people", "1500 dinner shared with Alice and Bob")
- CHECK_DEBTS: Asking who owes money (e.g., "who owes me?", "my debts", "does Rahul owe me?")
- SETTLE_DEBT: Marking a debt as paid (e.g., "Rahul paid me back", "cleared debt from Alice")
- ADD_CATEGORY: Creating a new category (e.g., "add category Subscriptions")
- LIST_CATEGORIES: Viewing categories (e.g., "show my categories")
- DELETE_EXPENSE: Deleting an expense (e.g., "delete the last expense")
- HELP: Asking for help or commands (e.g., "help", "what can you do?")
- UNKNOWN: Only use this if the message is completely unrelated to expenses or unsupported.

If the user is replying to a previous message or implicitly confirming something, use the conversation history to determine the intent. Wait, if they just say "yes" or "ok", it usually implies continuing the previous flow or UNKNOWN if no active flow.
Return the structured JSON representation of the user's intent."""

        messages = [SystemMessage(content=system_prompt)]
        
        if history:
            for msg in history:
                if msg["role"] == "user":
                    messages.append(HumanMessage(content=msg["content"]))
                else:
                    # We can use SystemMessage or AIMessage for Assistant history
                    # Using AIMessage is better, but since history is dict, we adapt
                    pass # Handled by the agent builder or we can map them here
                    
            # Better: let's map the history strings if provided
            for msg in history:
                if msg["role"] == "user":
                    messages.append(HumanMessage(content=msg["content"]))
                else:
                    # just append as context
                    messages.append(SystemMessage(content=f"Assistant previously said: {msg['content']}"))

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
                split_people=None,
                person_name=result.person_name,
                time_range=result.time_range,
                raw_text=text,
            )
        except Exception as e:
            logger.error("LLM intent classification failed", error=str(e), exc_info=True)
            # Safe fallback
            return ParsedMessage(intent=Intent.UNKNOWN, raw_text=text)
