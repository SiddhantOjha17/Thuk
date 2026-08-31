"""Tests for get_instant_intent and parse_amount utilities."""

from decimal import Decimal

import pytest

from app.processors.text_parser import Intent, get_instant_intent
from app.utils.currency import parse_amount, detect_currency


# ── get_instant_intent ────────────────────────────────────────────────────────

class TestInstantIntent:
    def test_help(self):
        assert get_instant_intent("help") == Intent.HELP
        assert get_instant_intent("?") == Intent.HELP
        assert get_instant_intent("HELP") == Intent.HELP

    def test_export(self):
        assert get_instant_intent("export") == Intent.EXPORT_EXPENSES
        assert get_instant_intent("export my expenses") == Intent.EXPORT_EXPENSES
        assert get_instant_intent("download csv") == Intent.EXPORT_EXPENSES

    def test_list_categories(self):
        assert get_instant_intent("show categories") == Intent.LIST_CATEGORIES
        assert get_instant_intent("my category") == Intent.LIST_CATEGORIES
        assert get_instant_intent("list categories") == Intent.LIST_CATEGORIES

    def test_delete_last(self):
        assert get_instant_intent("delete last expense") == Intent.DELETE_EXPENSE
        assert get_instant_intent("delete last") == Intent.DELETE_EXPENSE

    def test_budget_check(self):
        assert get_instant_intent("budget status") == Intent.CHECK_BUDGET
        assert get_instant_intent("my budget") == Intent.CHECK_BUDGET
        assert get_instant_intent("check budget") == Intent.CHECK_BUDGET

    def test_set_budget(self):
        assert get_instant_intent("set budget 10000") == Intent.SET_BUDGET
        assert get_instant_intent("set budget 5000") == Intent.SET_BUDGET

    def test_ambiguous_returns_none(self):
        """Anything ambiguous must return None so the LLM handles it."""
        assert get_instant_intent("500 food") is None
        assert get_instant_intent("yes") is None
        assert get_instant_intent("actually make it 600") is None
        assert get_instant_intent("how much did I spend") is None
        assert get_instant_intent("add category Gym") is None
        assert get_instant_intent("Rahul paid me back") is None
        assert get_instant_intent("split 1000 with 3 people") is None
        # "set budget" without a number is ambiguous
        assert get_instant_intent("set budget") is None


# ── parse_amount ──────────────────────────────────────────────────────────────

class TestParseAmount:
    def test_plain_integer(self):
        assert parse_amount("500 food") == Decimal("500")
        assert parse_amount("1200") == Decimal("1200")

    def test_k_shorthand(self):
        assert parse_amount("2.5k rent") == Decimal("2500")
        assert parse_amount("10k food") == Decimal("10000")
        assert parse_amount("0.5k chai") == Decimal("500")
        assert parse_amount("10K groceries") == Decimal("10000")

    def test_currency_prefix(self):
        assert parse_amount("₹850 uber") == Decimal("850")
        assert parse_amount("$20 netflix") == Decimal("20")

    def test_comma_formatted(self):
        # Standard 3-digit grouping is handled by the regex
        assert parse_amount("1,500 groceries") == Decimal("1500")
        assert parse_amount("₹10,000 rent") == Decimal("10000")
        # Indian 2-digit grouping (₹1,00,000) is intentionally left to the LLM

    def test_decimal_amount(self):
        assert parse_amount("49.99 subscription") == Decimal("49.99")

    def test_no_amount(self):
        assert parse_amount("help") is None
        assert parse_amount("show categories") is None
        assert parse_amount("yes") is None

    def test_written_numbers_return_none(self):
        """Written-out numbers are handled by the LLM, not the regex."""
        assert parse_amount("five hundred rupees") is None


# ── detect_currency ───────────────────────────────────────────────────────────

class TestDetectCurrency:
    def test_default_inr(self):
        assert detect_currency("500 food") == "INR"

    def test_rupee_symbol(self):
        assert detect_currency("₹850 uber") == "INR"

    def test_dollar(self):
        assert detect_currency("$20 netflix") == "USD"
        assert detect_currency("20 dollars") == "USD"

    def test_euro(self):
        assert detect_currency("€50 dinner") == "EUR"
