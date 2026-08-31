"""Intent types, ParsedMessage dataclass, and a tiny instant-intent fast-path.

The heavy lifting (entity extraction, Hinglish, contextual replies) is done by
the LLM-based IntentClassifier. This module only handles:
  1. The shared Intent enum and ParsedMessage dataclass.
  2. get_instant_intent() — a zero-LLM shortcut for 6 crystal-clear commands.
  3. parse_amount / detect_currency utilities (imported from currency.py).
"""

import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import Enum

from app.utils.currency import detect_currency, parse_amount

__all__ = [
    "Intent",
    "ParsedMessage",
    "get_instant_intent",
    "parse_amount",
    "detect_currency",
]


class Intent(str, Enum):
    """User intent classification."""

    ADD_EXPENSE = "add_expense"
    QUERY_EXPENSES = "query_expenses"
    SPLIT_PAYMENT = "split_payment"
    CHECK_DEBTS = "check_debts"
    SETTLE_DEBT = "settle_debt"
    ADD_CATEGORY = "add_category"
    LIST_CATEGORIES = "list_categories"
    DELETE_EXPENSE = "delete_expense"
    EDIT_EXPENSE = "edit_expense"
    SET_BUDGET = "set_budget"
    CHECK_BUDGET = "check_budget"
    EXPORT_EXPENSES = "export_expenses"
    RESOLVE_CATEGORY = "resolve_category"
    CLARIFY = "clarify"
    HELP = "help"
    UNKNOWN = "unknown"


@dataclass
class ParsedMessage:
    """Parsed message with extracted entities."""

    intent: Intent
    amount: Decimal | None = None
    currency: str = "INR"
    description: str | None = None
    category_hint: str | None = None
    expense_date: date | None = None
    split_count: int | None = None
    split_people: list[str] | None = None
    person_name: str | None = None
    time_range: str | None = None
    extracted_category_name: str | None = None
    edit_instructions: str | None = None
    raw_text: str = ""


# ---------------------------------------------------------------------------
# Instant-intent fast-path — zero LLM calls for obvious commands
# ---------------------------------------------------------------------------

_INSTANT_ROUTES: list[tuple[re.Pattern, Intent]] = [
    # help
    (re.compile(r"^(help|\?)$", re.IGNORECASE), Intent.HELP),
    # export / download CSV
    (re.compile(r"^(export|download\s+csv|send\s+(me\s+)?csv|export\s+my\s+expenses?)$", re.IGNORECASE), Intent.EXPORT_EXPENSES),
    # list / show categories
    (re.compile(r"^(show|list|my)\s+categor(y|ies)$", re.IGNORECASE), Intent.LIST_CATEGORIES),
    # exact delete last expense
    (re.compile(r"^delete\s+last(\s+expense)?$", re.IGNORECASE), Intent.DELETE_EXPENSE),
    # check budget status
    (re.compile(r"^(check\s+)?(my\s+)?budget(\s+status)?$", re.IGNORECASE), Intent.CHECK_BUDGET),
    # set budget <amount>  — only when a clear number follows
    (re.compile(r"^set\s+budget\s+\d", re.IGNORECASE), Intent.SET_BUDGET),
]


def get_instant_intent(text: str) -> Intent | None:
    """Return an Intent for crystal-clear commands, or None if LLM is needed.

    Called before the LLM so that ~6 unambiguous commands never consume a
    free-tier API request.

    Args:
        text: The raw message text (will be stripped internally).

    Returns:
        An Intent if the message is unambiguous, else None.
    """
    stripped = text.strip()
    for pattern, intent in _INSTANT_ROUTES:
        if pattern.match(stripped):
            return intent
    return None
