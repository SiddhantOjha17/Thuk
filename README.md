# Thuk - WhatsApp Expense Tracker Bot

A multi-agent WhatsApp bot that tracks expenses via text, image (bank transaction screenshots), and voice recordings.

## Features

- 📝 **Text Input**: "Spent ₹500 on food"
- 📸 **Image Input**: Screenshot of bank transaction messages
- 🎤 **Voice Input**: Voice notes describing expenses
- 💰 **Split Payments**: Track shared expenses and IOUs
- 📊 **Analytics**: Query expenses by date, category, etc.
- 🏷️ **Custom Categories**: Add your own expense categories
- 💱 **Multi-Currency**: Support for multiple currencies

## Setup

### Prerequisites

- Python 3.11+
- PostgreSQL database
- Twilio account (for WhatsApp)
- OpenAI API key (each user provides their own)

### Installation

1. Clone the repository
2. Install dependencies:
   ```bash
   pip install -e .
   ```

3. Copy `.env.example` to `.env` and fill in your configuration:
   ```bash
   cp .env.example .env
   ```

4. Run database migrations:
   ```bash
   alembic upgrade head
   ```

5. Start the server:
   ```bash
   uvicorn app.main:app --reload
   ```

## Environment Variables

See `.env.example` for all configuration options.

## Architecture

The bot uses a multi-agent system built with LangGraph:

- **Supervisor Agent**: Routes messages and maintains conversation context
- **Expense Agent**: Handles expense CRUD operations
- **Query Agent**: Analytics and spending reports
- **Split Agent**: Manages split payments and debts
- **Category Agent**: Custom category management

## Deployment

Deploy to Render with the included configuration files.

## License

MIT
