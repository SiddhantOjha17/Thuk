"""Supervisor Agent - orchestrates the multi-agent system using LangGraph."""

import asyncio
from typing import Annotated, Literal

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from typing_extensions import TypedDict

from app.agents.budget_agent import BudgetAgent
from app.agents.category_agent import CategoryAgent
from app.agents.expense_agent import ExpenseAgent
from app.agents.split_agent import SplitAgent
from app.agents.text2sql_agent import Text2SQLAgent
from app.agents.export_agent import ExportAgent
from app.agents.intent_classifier import IntentClassifier
from app.memory.redis_store import store
from app.processors.text_parser import Intent, ParsedMessage, TextParser
from app.utils.encryption import decrypt_api_key
from app.utils.logging import get_logger
from app.whatsapp.handlers import get_help_message

logger = get_logger(__name__)


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
        self.expense_agent = ExpenseAgent()
        self.query_agent = Text2SQLAgent(user)
        self.split_agent = SplitAgent()
        self.category_agent = CategoryAgent()
        self.budget_agent = BudgetAgent()
        self.export_agent = ExportAgent()
        
        # Intent Router fallback
        self.intent_classifier = IntentClassifier(user)
        
        # Compile workflow once per agent instance
        self.app = self.build_graph().compile()

    async def route_message(self, state: AgentState) -> AgentState:
        """Parse message and determine routing using LLM logic."""
        # Intercept category resolution flow (stateful manual override)
        is_pending_expense = await store.get_flag(self.user.phone_number, "pending_expense")
        if is_pending_expense:
            state["parsed"] = ParsedMessage(intent=Intent.RESOLVE_CATEGORY, raw_text=state["user_message"])
            return state

        # Fully LLM-driven Intent Parsing for everything else
        history = await store.get_history(self.user.phone_number, limit=6)
        parsed = await self.intent_classifier.classify(state["user_message"], history)
            
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
            Intent.RESOLVE_CATEGORY: "expense_resolve",
            Intent.DELETE_EXPENSE: "expense_delete",
            Intent.EDIT_EXPENSE: "expense_edit",
            Intent.SET_BUDGET: "budget_set",
            Intent.CHECK_BUDGET: "budget_check",
            Intent.EXPORT_EXPENSES: "export",
            Intent.HELP: "help",
            Intent.CLARIFY: "clarify",
            Intent.UNKNOWN: "llm_fallback",
        }

        return routing.get(intent, "llm_fallback")

    async def handle_expense(self, state: AgentState) -> AgentState:
        """Handle expense addition."""
        # We need history for contextual category detection
        history_dicts = await store.get_history(self.user.phone_number, limit=6)
        
        response = await self.expense_agent.add_expense(
            db=state["db"],
            user=state["user"],
            parsed=state["parsed"],
            source_type=state["source_type"],
            history=history_dicts,
        )
        
        # Check budget warning if expense added
        if "Added expense" in response:
            warning = await self.budget_agent.check_budget(state["db"], state["user"])
            if warning:
                response += f"\n\n{warning}"
                
        state["response"] = response
        return state

    async def handle_expense_category_resolve(self, state: AgentState) -> AgentState:
        """Handle resolving an ambiguous category."""
        response = await self.expense_agent.resolve_pending(
            db=state["db"],
            user=state["user"],
            reply_text=state["user_message"],
        )
        
        # Check budget warning if expense added
        if "Added expense" in response:
            warning = await self.budget_agent.check_budget(state["db"], state["user"])
            if warning:
                response += f"\n\n{warning}"
                
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

    async def handle_expense_edit(self, state: AgentState) -> AgentState:
        """Handle editing the last expense."""
        parsed = state["parsed"]
        response = await self.expense_agent.edit_last(
            db=state["db"],
            user=state["user"],
            instructions=parsed.edit_instructions or state["user_message"],
        )
        state["response"] = response
        return state

    async def handle_budget_set(self, state: AgentState) -> AgentState:
        """Handle setting a monthly budget."""
        parsed = state["parsed"]
        if not parsed.amount:
            response = "Please provide a budget amount, e.g., 'set budget 5000'."
        else:
            response = await self.budget_agent.set_budget(
                db=state["db"],
                user=state["user"],
                amount=parsed.amount,
                currency=parsed.currency,
            )
        state["response"] = response
        return state

    async def handle_budget_check(self, state: AgentState) -> AgentState:
        """Handle checking the monthly budget."""
        response = await self.budget_agent.get_budget_status(
            db=state["db"],
            user=state["user"],
        )
        state["response"] = response
        return state

    async def handle_export(self, state: AgentState) -> AgentState:
        """Handle CSV export."""
        # For simplicity in graph, we use a generic request URL, this can be improved
        # or we just rely on the fallback webhook base_url setting.
        response = await self.export_agent.export_and_get_url(
            db=state["db"],
            user=state["user"],
            request_base_url="https://thuk.fly.dev" # fallback
        )
        state["response"] = response
        return state

    async def handle_query(self, state: AgentState) -> AgentState:
        """Handle expense queries using Text2SQL analytics."""
        response = await self.query_agent.execute_query(
            db=state["db"],
            natural_query=state["user_message"],
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
        name = state["parsed"].extracted_category_name
        
        if name:
            response = await self.category_agent.add_category(
                db=state["db"],
                user=state["user"],
                name=name,
            )
        else:
            response = "Please specify a category name (e.g., 'Add a category for Gym')."
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

    async def handle_clarify(self, state: AgentState) -> AgentState:
        """Handle intentionally ambiguous queries where the LLM requires clarification."""
        clarification = state["parsed"].raw_text if state["parsed"] and state["parsed"].raw_text else "I didn't quite catch that. Could you please clarify what you mean?"
        state["response"] = clarification
        return state

    async def handle_llm_fallback(self, state: AgentState) -> AgentState:
        """Last resort - try to handle as expense, or give a minimal help message."""
        msg = state["user_message"]
        
        # Check if there's any number in the message - if so, try to route to expense
        import re
        if re.search(r'\d+', msg):
            # Has a number, probably an expense - try expense handler
            history = await store.get_history(self.user.phone_number, limit=6)
            reclassified = await self.intent_classifier.classify(
                f"ADD_EXPENSE OVERRIDE: The user wants to add this expense: {msg}", history
            )
            reclassified.intent = Intent.ADD_EXPENSE
            if reclassified.amount is None:
                # Try to extract a number
                nums = re.findall(r'[\d]+(?:\.[\d]+)?', msg)
                if nums:
                    from decimal import Decimal
                    reclassified.amount = Decimal(nums[0])
            if reclassified.description is None:
                reclassified.description = msg
            state["parsed"] = reclassified
            return await self.handle_expense(state)
        
        state["response"] = "I didn't quite understand that. Try something like 'Spent 500 on food' or type 'help' to see all commands."
        return state

    def build_graph(self) -> StateGraph:
        """Build the LangGraph workflow."""
        workflow = StateGraph(AgentState)

        # Add nodes
        workflow.add_node("router", self.route_message)
        workflow.add_node("expense", self.handle_expense)
        workflow.add_node("expense_delete", self.handle_expense_delete)
        workflow.add_node("expense_edit", self.handle_expense_edit)
        workflow.add_node("expense_resolve", self.handle_expense_category_resolve)
        workflow.add_node("budget_set", self.handle_budget_set)
        workflow.add_node("budget_check", self.handle_budget_check)
        workflow.add_node("export", self.handle_export)
        workflow.add_node("query", self.handle_query)
        workflow.add_node("split", self.handle_split)
        workflow.add_node("debts", self.handle_debts)
        workflow.add_node("settle", self.handle_settle)
        workflow.add_node("category_add", self.handle_category_add)
        workflow.add_node("category_list", self.handle_category_list)
        workflow.add_node("help", self.handle_help)
        workflow.add_node("clarify", self.handle_clarify)
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
                "expense_edit": "expense_edit",
                "expense_resolve": "expense_resolve",
                "budget_set": "budget_set",
                "budget_check": "budget_check",
                "export": "export",
                "query": "query",
                "split": "split",
                "debts": "debts",
                "settle": "settle",
                "category_add": "category_add",
                "category_list": "category_list",
                "help": "help",
                "clarify": "clarify",
                "llm_fallback": "llm_fallback",
            },
        )

        # All agents end after processing
        for node in ["expense", "expense_delete", "expense_edit", "expense_resolve", "budget_set", "budget_check", "export",
                     "query", "split", "debts", "settle", "category_add", 
                     "category_list", "help", "clarify", "llm_fallback"]:
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
        # Load history
        history_dicts = await store.get_history(self.user.phone_number, limit=6)
        messages = []
        for msg in history_dicts:
            if msg["role"] == "user":
                messages.append(HumanMessage(content=msg["content"]))
            else:
                messages.append(AIMessage(content=msg["content"]))

        initial_state: AgentState = {
            "messages": messages,
            "user_message": message,
            "parsed": None,
            "response": "",
            "user": self.user,
            "db": db,
            "source_type": source_type,
        }

        try:
            # 30-second timeout for the entire agent workflow
            result = await asyncio.wait_for(self.app.ainvoke(initial_state), timeout=30.0)
            
            response_text = result["response"]
            
            # Save messages on success
            await store.add_message(self.user.phone_number, "user", message)
            await store.add_message(self.user.phone_number, "assistant", response_text)
            
            return response_text
        except asyncio.TimeoutError:
            logger.error("Agent workflow timed out", user_id=str(self.user.id))
            await db.rollback()
            return "The request took too long to process. Please try again."
        except Exception as e:
            logger.error("Error in agent workflow", error=str(e), user_id=str(self.user.id), exc_info=True)
            await db.rollback()
            return "Sorry, I encountered an internal error processing your request."
