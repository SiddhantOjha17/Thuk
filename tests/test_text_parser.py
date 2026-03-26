"""Tests for TextParser intent detection."""

from decimal import Decimal

from app.processors.text_parser import Intent, TextParser


def test_add_expense_parsing():
    """Test parsing expense addition."""
    parser = TextParser()
    
    # Simple explicit intent
    parsed = parser.parse("Spent 500 on coffee")
    assert parsed.intent == Intent.ADD_EXPENSE
    assert parsed.amount == Decimal("500")
    assert parsed.description == "coffee"
    assert parsed.category_hint == "Food"
    
    # Implicit expense (just amount)
    parsed = parser.parse("2500 for internet bill")
    assert parsed.intent == Intent.ADD_EXPENSE
    assert parsed.amount == Decimal("2500")
    assert parsed.description == "internet bill"
    assert parsed.category_hint == "Bills"
    
    # Different currencies
    parsed = parser.parse("Paid $50 for netflix")
    assert parsed.intent == Intent.ADD_EXPENSE
    assert parsed.amount == Decimal("50")
    assert parsed.currency == "USD"


def test_intent_detection():
    """Test regex intent detection fallback."""
    parser = TextParser()
    
    # Delete
    assert parser.parse("delete last expense").intent == Intent.DELETE_EXPENSE
    assert parser.parse("undo that").intent == Intent.DELETE_EXPENSE
    
    # Split
    assert parser.parse("1000 dinner split with 4 people").intent == Intent.SPLIT_PAYMENT
    assert parser.parse("divide 500 among 3").intent == Intent.SPLIT_PAYMENT
    
    # Category list/add
    assert parser.parse("list my categories").intent == Intent.LIST_CATEGORIES
    assert parser.parse("add category Shopping").intent == Intent.ADD_CATEGORY
    
    # Query
    assert parser.parse("how much did I spend this week?").intent == Intent.QUERY_EXPENSES
    assert parser.parse("show my expenses today").intent == Intent.QUERY_EXPENSES
    
    # Budget
    assert parser.parse("set budget 10000").intent == Intent.SET_BUDGET
    assert parser.parse("check my budget status").intent == Intent.CHECK_BUDGET
    
    # Export
    assert parser.parse("export my expenses to csv").intent == Intent.EXPORT_EXPENSES
    
    # Edit
    assert parser.parse("edit last expense to 400").intent == Intent.EDIT_EXPENSE
    
    # Help
    assert parser.parse("help").intent == Intent.HELP
    assert parser.parse("what can you do?").intent == Intent.UNKNOWN # Should hit UNKNOWN -> IntentClassifier LLM
    
    
def test_complex_amounts():
    """Test complex amount parsing."""
    parser = TextParser()
    
    assert parser.parse("spent 1,500.50").amount == Decimal("1500.50")
    assert parser.parse("paid 2.5k for food").amount == Decimal("2500")
    assert parser.parse("10k rent").amount == Decimal("10000")
    assert parser.parse("0.5k").amount == Decimal("500")
