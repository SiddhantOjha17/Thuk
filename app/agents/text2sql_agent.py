"""Text-to-SQL Agent for natural language data querying."""

from datetime import date
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.utils.encryption import decrypt_api_key
from app.utils.logging import get_logger

logger = get_logger(__name__)


class Text2SQLAgent:
    """Agent for translating natural language queries into secure SQL."""

    def __init__(self, user):
        """Initialize with user's specific API key."""
        self.user = user
        api_key = decrypt_api_key(user.openai_api_key_encrypted)
        
        # Fast, cheap model is perfect for SQL generation
        self.sql_llm = ChatOpenAI(
            api_key=api_key,
            model="gpt-4o-mini",
            temperature=0,
        )
        
        # Same model for response generation
        self.response_llm = ChatOpenAI(
            api_key=api_key,
            model="gpt-4o-mini",
            temperature=0.7,
        )

    async def _generate_sql(self, query: str) -> str:
        """Use LLM to generate PostgreSQL query."""
        today = date.today().isoformat()
        
        schema = """
Table: expenses
Columns:
- amount (Numeric)
- currency (String)
- description (Text)
- category_id (UUID, nullable, Foreign Key to categories.id)
- expense_date (Date)
- created_at (DateTime)
- user_id (UUID, Foreign Key)

Table: categories
Columns:
- id (UUID)
- name (String, e.g. 'Food', 'Transport')
- is_default (Boolean)
- user_id (UUID, nullable)
"""

        system_prompt = f"""You are a Postgres Expert Analytics System. Convert the user's natural language question into a read-only PostgreSQL query.
Today's date is {today}.

DATABASE SCHEMA:
{schema}

CRITICAL RULES:
1. Return ONLY the raw SQL query. Do not wrap it in ```sql markdown or add any chat text!
2. You MUST strictly filter by the requesting user. Add `WHERE user_id = :user_id` or `AND e.user_id = :user_id` in your joins appropriately.
3. NEVER make destructive updates (No INSERT, UPDATE, DELETE, DROP).
4. For categories, perform a LEFT JOIN (e.g., `LEFT JOIN categories c ON e.category_id = c.id`). If category is NULL, it means "Others".
5. Use date functions appropriately (e.g., `e.expense_date >= current_date - interval '7 days'`).
"""
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=query)
        ]

        result = await self.sql_llm.ainvoke(messages)
        return result.content.strip().replace("```sql", "").replace("```", "").strip()

    async def execute_query(self, db: AsyncSession, natural_query: str) -> str:
        """Generate SQL, execute it securely, and format the response."""
        try:
            # 1. Generate SQL
            sql_query = await self._generate_sql(natural_query)
            
            # Security Sanity Check (Very basic guardrail)
            if not sql_query.lower().lstrip().startswith("select"):
                logger.warning(f"Prevented non-select query: {sql_query}")
                return "I can only perform safe analytics queries. The generated query was invalid."

            # 2. Execute SQL securely with mapped parameter
            stmt = text(sql_query)
            result_proxy = await db.execute(stmt, {"user_id": self.user.id})
            
            # Ensure safe conversion of objects like decimals/dates to string
            rows = result_proxy.fetchall()
            
            # Convert row tuples to list of dicts for LLM ingestion
            keys = result_proxy.keys()
            results_list = [dict(zip(keys, row)) for row in rows]
            
            # 3. Format results beautifully using LLM
            format_prompt = f"""You are Thuk's friendly analytics voice.
The user originally asked: "{natural_query}"

I executed a SQL query to get the raw data from their personal database.
Here are the raw JSON results:
{results_list}

Please formulate a very brief, friendly, perfectly formatted WhatsApp message responding to their query based ON THIS EXACT DATA. 
- Do not use emojis. 
- Format numbers beautifully (e.g. 1500 -> 1,500).
- If the result list is empty, kindly state that no records match.
- Use bullet points if there are multiple rows.
"""
            final_response = await self.response_llm.ainvoke([SystemMessage(content=format_prompt)])
            return final_response.content

        except Exception as e:
            logger.error(f"Text2SQL execution failed. Query: {natural_query}", error=str(e), exc_info=True)
            return "Sorry! My analytics engine hit a snag while trying to calculate that specific query."
