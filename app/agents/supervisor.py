"""Supervisor Agent - orchestrates the multi-agent system using LangGraph."""

from typing import Annotated, Literal

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from typing_extensions import TypedDict

from app.agents.category_agent import CategoryAgent
from app.agents.expense_agent import ExpenseAgent
from app.agents.query_agent import QueryAgent
from app.agents.split_agent import SplitAgent
from app.processors.text_parser import Intent, ParsedMessage, TextParser
from app.utils.encryption import decrypt_api_key
from app.whatsapp.handlers import get_help_message


class AgentState(TypedDict):
    """State passed between agents in the graph."""

    messages: Annotated[list, add_messages]
    user_message: str
    parsed: ParsedMessage | None
    response: str
    user: object
    db: AsyncSession
    source_type: str


class SupervisorAgent:
    """Main orchestrator that routes messages to appropriate agents."""

    def __init__(self, user):
        """Initialize with user's API key."""
        self.user = user
        api_key = decrypt_api_key(user.openai_api_key_encrypted)
        self.llm = ChatOpenAI(
            api_key=api_key,
            model="gpt-4o-mini",
            temperature=0,
        )
        self.text_parser = TextParser()
        self.expense_agent = ExpenseAgent()
        self.query_agent = QueryAgent()
        self.split_agent = SplitAgent()
        self.category_agent = CategoryAgent()

    async def route_message(self, state: AgentState) -> AgentState:
        """Parse message and determine routing."""
        parsed = self.text_parser.parse(state["user_message"])
        state["parsed"] = parsed
        return state

    def get_next_agent(self, state: AgentState) -> str:
        """Determine which agent should handle the message."""
        if state["parsed"] is None:
            return "llm_fallback"

        intent = state["parsed"].intent

        routing = {
            Intent.ADD_EXPENSE: "expense",
            Intent.DELETE_EXPENSE: "expense_delete",
            Intent.QUERY_EXPENSES: "query",
            Intent.SPLIT_PAYMENT: "split",
            Intent.CHECK_DEBTS: "debts",
            Intent.SETTLE_DEBT: "settle",
            Intent.ADD_CATEGORY: "category_add",
            Intent.LIST_CATEGORIES: "category_list",
            Intent.HELP: "help",
            Intent.UNKNOWN: "llm_fallback",
        }

        return routing.get(intent, "llm_fallback")

    async def handle_expense(self, state: AgentState) -> AgentState:
        """Handle expense addition."""
        response = await self.expense_agent.add_expense(
            db=state["db"],
            user=state["user"],
            parsed=state["parsed"],
            source_type=state["source_type"],
        )
        state["response"] = response
        return state

    async def handle_expense_delete(self, state: AgentState) -> AgentState:
        """Handle expense deletion."""
        response = await self.expense_agent.delete_last(
            db=state["db"],
            user=state["user"],
        )
        state["response"] = response
        return state

    async def handle_query(self, state: AgentState) -> AgentState:
        """Handle expense queries."""
        response = await self.query_agent.get_summary(
            db=state["db"],
            user=state["user"],
            parsed=state["parsed"],
        )
        state["response"] = response
        return state

    async def handle_split(self, state: AgentState) -> AgentState:
        """Handle split payment creation."""
        response = await self.split_agent.create_split_expense(
            db=state["db"],
            user=state["user"],
            parsed=state["parsed"],
            source_type=state["source_type"],
        )
        state["response"] = response
        return state

    async def handle_debts(self, state: AgentState) -> AgentState:
        """Handle debt summary query."""
        response = await self.split_agent.get_debt_summary(
            db=state["db"],
            user=state["user"],
        )
        state["response"] = response
        return state

    async def handle_settle(self, state: AgentState) -> AgentState:
        """Handle debt settlement."""
        if state["parsed"] and state["parsed"].person_name:
            response = await self.split_agent.settle_debt(
                db=state["db"],
                user=state["user"],
                person_name=state["parsed"].person_name,
            )
        else:
            response = "Please specify who paid you back (e.g., 'Rahul paid me back')."
        state["response"] = response
        return state

    async def handle_category_add(self, state: AgentState) -> AgentState:
        """Handle category addition."""
        name = self.category_agent.extract_category_name(state["user_message"])
        if name:
            response = await self.category_agent.add_category(
                db=state["db"],
                user=state["user"],
                name=name,
            )
        else:
            response = "Please specify a category name (e.g., 'add category Subscriptions')."
        state["response"] = response
        return state

    async def handle_category_list(self, state: AgentState) -> AgentState:
        """Handle category listing."""
        response = await self.category_agent.list_categories(
            db=state["db"],
            user=state["user"],
        )
        state["response"] = response
        return state

    async def handle_help(self, state: AgentState) -> AgentState:
        """Handle help request."""
        state["response"] = get_help_message()
        return state

    async def handle_llm_fallback(self, state: AgentState) -> AgentState:
        """Use LLM for ambiguous messages."""
        # Create context-aware prompt
        system_prompt = """You are Thuk, a friendly WhatsApp expense tracker bot.

The user sent a message that wasn't clearly understood. Help them by:
1. Acknowledging their message
2. Suggesting how they might rephrase it
3. Providing examples of supported commands

Keep responses concise and friendly. Do not use emojis.

Supported actions:
- Add expenses: "Spent 500 on food"
- Query expenses: "How much did I spend today?"
- Split payments: "2000 split with 4 people"
- Check debts: "Who owes me?"
- Settle debts: "Rahul paid me back"
- Categories: "Add category Subscriptions" or "Show my categories"
- Delete: "Delete last expense"
"""

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=state["user_message"]),
        ]

        response = await self.llm.ainvoke(messages)
        state["response"] = response.content
        return state

    def build_graph(self) -> StateGraph:
        """Build the LangGraph workflow."""
        workflow = StateGraph(AgentState)

        # Add nodes
        workflow.add_node("router", self.route_message)
        workflow.add_node("expense", self.handle_expense)
        workflow.add_node("expense_delete", self.handle_expense_delete)
        workflow.add_node("query", self.handle_query)
        workflow.add_node("split", self.handle_split)
        workflow.add_node("debts", self.handle_debts)
        workflow.add_node("settle", self.handle_settle)
        workflow.add_node("category_add", self.handle_category_add)
        workflow.add_node("category_list", self.handle_category_list)
        workflow.add_node("help", self.handle_help)
        workflow.add_node("llm_fallback", self.handle_llm_fallback)

        # Set entry point
        workflow.set_entry_point("router")

        # Add conditional edges from router
        workflow.add_conditional_edges(
            "router",
            self.get_next_agent,
            {
                "expense": "expense",
                "expense_delete": "expense_delete",
                "query": "query",
                "split": "split",
                "debts": "debts",
                "settle": "settle",
                "category_add": "category_add",
                "category_list": "category_list",
                "help": "help",
                "llm_fallback": "llm_fallback",
            },
        )

        # All agents end after processing
        for node in ["expense", "expense_delete", "query", "split", "debts",
                     "settle", "category_add", "category_list", "help", "llm_fallback"]:
            workflow.add_edge(node, END)

        return workflow

    async def process(
        self,
        message: str,
        db: AsyncSession,
        source_type: str = "text",
    ) -> str:
        """Process a message through the agent system.

        Args:
            message: The user's message
            db: Database session
            source_type: Source of the message (text/image/voice)

        Returns:
            Response message
        """
        workflow = self.build_graph()
        app = workflow.compile()

        initial_state: AgentState = {
            "messages": [],
            "user_message": message,
            "parsed": None,
            "response": "",
            "user": self.user,
            "db": db,
            "source_type": source_type,
        }

        result = await app.ainvoke(initial_state)
        return result["response"]
