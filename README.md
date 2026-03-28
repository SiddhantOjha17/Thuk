# Thuk - Intelligent WhatsApp Expense Tracker Bot

A multi-agent WhatsApp bot that tracks expenses via natural language text, voice recordings, and image receipts. Thuk uses LangGraph and OpenAI to provide a robust, state-of-the-art conversational interface for managing your personal finances.

## Key Features

- **Natural Language Input**: "Spent ₹500 on food" or "1200 for 2 movie tickets"
- **Image & Voice**: Screenshot of bank transaction messages or voice notes.
- **Split Payments**: Track shared expenses and IOUs ("paid 1500 for dinner split with Alice and Bob").
- **Interactive Category Fallbacks**: If the AI is unsure about a category, it will pause and prompt you with an interactive numbered list. Try typing typos or completely new categories and it handles them cleanly!
- **Smart Descriptions**: Extracts beautiful 'short descriptions' dynamically for your expenses using GPT-4o-Mini (e.g., "football turf" or "netflix subscription").
- **Budgeting System**: Set monthly budgets and get automatic warnings when you cross specific thresholds ("set budget to 50000").
- **Rich Analytics**: Query expenses by date ("how much did I spend this week?"). The `/summary` correctly groups unassigned expenses into "Others".
- **CSV Exports**: Export your monthly expenses directly to a downloadable CSV via WhatsApp ("export my expenses").
- **Memory & Context**: Remembers the last 6 messages utilizing Redis, so you can reply contextually (e.g., "delete that", "actually make it 600", "yes").
- **Secure**: Every user provides their own OpenAI API Key which is encrypted at rest in the database.

## Architecture

The bot uses a multi-agent routing system built on top of **LangGraph**:

- **Supervisor Agent**: Maintains conversation context via Upstash Redis and routes messages using `IntentClassifier`.
- **Expense Agent**: Handles expense operations, AI short-description extraction, and interactive category resolution.
- **Budget Agent**: Sets and monitors monthly financial alerts.
- **Query Agent**: Serves analytics and spending summaries.
- **Split Agent**: Manages multi-user split payments and unsettled debts.
- **Export Agent**: Generates CSV reports and serves them securely.

## Setup & Local Development

### Prerequisites

- Python 3.11+
- PostgreSQL database
- Upstash Redis database (or local Redis instance)
- Twilio account (for WhatsApp API Sandbox/Production)
- OpenAI API key (for agentic routing and LLM extractions)

### Installation

1. Clone the repository and install dependencies using `uv` or `pip`:
   ```bash
   pip install -e .
   ```

2. Copy `.env.example` to `.env` and configure your credentials:
   ```bash
   cp .env.example .env
   # Ensure REDIS_URL, DATABASE_URL, ENCRYPTION_KEY, and TWILIO credentials are set
   ```

3. Run the database migrations (Alembic):
   ```bash
   alembic upgrade head
   ```

4. Start the FastAPI webhook server locally:
   ```bash
   uvicorn app.main:app --reload
   ```

## Deployment

Thuk is fully dockerized and configured for deployment on **Fly.io**:

1. Install the `flyctl` CLI.
2. Initialize or adjust `fly.toml` for your region.
3. Set your internal securely managed secrets:
   ```bash
   fly secrets set REDIS_URL="..." DATABASE_URL="..." TWILIO_WHATSAPP_NUMBER="..."
   ```
4. Deploy the application:
   ```bash
   fly deploy
   ```

## License

MIT License
