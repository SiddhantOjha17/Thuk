"""Text parser for extracting intent and entities from natural language."""

import re
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from enum import Enum

from app.utils.currency import detect_currency, parse_amount


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
    time_range: str | None = None  # "today", "yesterday", "this_week", "this_month"
    raw_text: str = ""


class TextParser:
    """Parse natural language text to extract expense-related information."""

    # Intent detection patterns
    EXPENSE_PATTERNS = [
        r"spent|paid|bought|expense|cost|charged",
    ]
    QUERY_PATTERNS = [
        r"how much|show|list|expenses?|spending|summary|tell me|what did i",
    ]
    SPLIT_PATTERNS = [
        r"split|divide|share|among|between|with \d+ people",
    ]
    DEBT_CHECK_PATTERNS = [
        r"who owes|owes me|owe me|my debts|debt summary|pending",
    ]
    DEBT_SETTLE_PATTERNS = [
        r"paid me|settled|paid back|cleared|received from",
    ]
    CATEGORY_PATTERNS = [
        r"add category|new category|create category",
    ]
    LIST_CATEGORY_PATTERNS = [
        r"my categories|list categories|show categories",
    ]
    DELETE_PATTERNS = [
        r"delete|remove|cancel|undo",
    ]

    # Category keywords - expanded for better detection
    CATEGORY_KEYWORDS = {
        "food": [
            # General food terms
            "food", "lunch", "dinner", "breakfast", "snack", "meal", "eat", "eating",
            # Restaurant/delivery
            "restaurant", "cafe", "coffee", "tea", "swiggy", "zomato", "ubereats", "doordash",
            # Specific foods (common)
            "sandwich", "burger", "pizza", "pasta", "noodles", "rice", "curry", "biryani",
            "dosa", "idli", "samosa", "paratha", "roti", "dal", "thali", "momos",
            "chicken", "mutton", "fish", "paneer", "salad", "soup", "bread",
            # Drinks
            "chai", "lassi", "juice", "smoothie", "milkshake", "beer", "wine", "drinks",
            # Desserts
            "ice cream", "icecream", "cake", "dessert", "sweet", "mithai", "gulab jamun",
            # Fast food chains
            "mcdonalds", "kfc", "dominos", "subway", "starbucks", "ccd", "mcd",
        ],
        "transport": [
            "uber", "ola", "cab", "taxi", "auto", "rickshaw", "bus", "metro", "train",
            "fuel", "petrol", "diesel", "gas", "transport", "travel", "flight", "ticket",
            "rapido", "bike", "scooter", "parking", "toll", "lyft",
        ],
        "shopping": [
            "shopping", "amazon", "flipkart", "myntra", "clothes", "shoes", "electronics",
            "buy", "purchase", "mall", "store", "market", "bazaar", "grocery", "groceries",
            "bigbasket", "blinkit", "zepto", "instamart", "dmart",
        ],
        "bills": [
            "bill", "electricity", "water", "gas", "internet", "wifi", "phone", "recharge",
            "rent", "emi", "loan", "insurance", "tax", "maintenance", "society",
        ],
        "entertainment": [
            "movie", "netflix", "spotify", "amazon prime", "hotstar", "game", "gaming",
            "concert", "show", "subscription", "youtube", "premium", "theatre", "cinema",
            "pvr", "inox", "bookmyshow",
        ],
        "health": [
            "medicine", "doctor", "hospital", "pharmacy", "medical", "health", "gym",
            "fitness", "yoga", "clinic", "lab", "test", "checkup", "apollo", "1mg",
            "pharmeasy", "netmeds",
        ],
    }

    # Time patterns
    TIME_PATTERNS = {
        "today": r"\btoday\b",
        "yesterday": r"\byesterday\b",
        "this_week": r"\bthis week\b|\bweek\b",
        "last_week": r"\blast week\b",
        "this_month": r"\bthis month\b|\bmonth\b",
        "last_month": r"\blast month\b",
    }

    def parse(self, text: str) -> ParsedMessage:
        """Parse a text message and extract intent and entities.

        Args:
            text: The raw message text

        Returns:
            ParsedMessage with extracted information
        """
        text_lower = text.lower().strip()
        result = ParsedMessage(intent=Intent.UNKNOWN, raw_text=text)

        # Check for help
        if text_lower in ["help", "?", "commands"]:
            result.intent = Intent.HELP
            return result

        # Detect intent
        result.intent = self._detect_intent(text_lower)

        # Extract amount and currency
        result.amount = parse_amount(text)
        result.currency = detect_currency(text)

        # Extract description
        result.description = self._extract_description(text)

        # Detect category hint
        result.category_hint = self._detect_category(text_lower)

        # Extract date
        result.expense_date = self._extract_date(text_lower)

        # Extract time range for queries
        result.time_range = self._extract_time_range(text_lower)

        # Extract split information
        if result.intent == Intent.SPLIT_PAYMENT:
            result.split_count, result.split_people = self._extract_split_info(text)

        # Extract person name for debt operations
        if result.intent in [Intent.SETTLE_DEBT, Intent.CHECK_DEBTS]:
            result.person_name = self._extract_person_name(text)

        return result

    def _detect_intent(self, text: str) -> Intent:
        """Detect the primary intent from text."""
        # Order matters - more specific patterns first
        if any(re.search(p, text) for p in self.DELETE_PATTERNS):
            return Intent.DELETE_EXPENSE

        if any(re.search(p, text) for p in self.DEBT_SETTLE_PATTERNS):
            return Intent.SETTLE_DEBT

        if any(re.search(p, text) for p in self.DEBT_CHECK_PATTERNS):
            return Intent.CHECK_DEBTS

        if any(re.search(p, text) for p in self.SPLIT_PATTERNS):
            return Intent.SPLIT_PAYMENT

        if any(re.search(p, text) for p in self.LIST_CATEGORY_PATTERNS):
            return Intent.LIST_CATEGORIES

        if any(re.search(p, text) for p in self.CATEGORY_PATTERNS):
            return Intent.ADD_CATEGORY

        if any(re.search(p, text) for p in self.QUERY_PATTERNS):
            return Intent.QUERY_EXPENSES

        if any(re.search(p, text) for p in self.EXPENSE_PATTERNS):
            return Intent.ADD_EXPENSE

        # If there's an amount, likely an expense
        if parse_amount(text):
            return Intent.ADD_EXPENSE

        return Intent.UNKNOWN

    def _extract_description(self, text: str) -> str | None:
        """Extract expense description from text."""
        # Remove amount patterns
        desc = re.sub(r"[₹$€£¥]\s*\d+(?:,\d{3})*(?:\.\d{1,2})?", "", text)
        desc = re.sub(r"\d+(?:,\d{3})*(?:\.\d{1,2})?\s*[₹$€£¥]", "", desc)
        desc = re.sub(r"(?:rs\.?|inr|usd|eur)\s*\d+", "", desc, flags=re.IGNORECASE)
        desc = re.sub(r"\d+\s*(?:rs\.?|rupees?|dollars?)", "", desc, flags=re.IGNORECASE)

        # Remove common verbs
        desc = re.sub(r"\b(spent|paid|bought|for|on)\b", "", desc, flags=re.IGNORECASE)

        # Remove time words
        desc = re.sub(r"\b(today|yesterday|last week|this week|this month)\b", "", desc, flags=re.IGNORECASE)

        # Clean up
        desc = re.sub(r"\s+", " ", desc).strip()

        return desc if desc else None

    def _detect_category(self, text: str) -> str | None:
        """Detect category from text keywords."""
        for category, keywords in self.CATEGORY_KEYWORDS.items():
            if any(kw in text for kw in keywords):
                return category.capitalize()
        return None

    def _extract_date(self, text: str) -> date | None:
        """Extract expense date from text."""
        today = date.today()

        if "yesterday" in text:
            return today - timedelta(days=1)

        # Look for specific dates like "on 15th" or "dec 20"
        # Basic pattern - can be enhanced
        match = re.search(r"(\d{1,2})(?:st|nd|rd|th)?\s*(?:of\s*)?(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)?", text, re.IGNORECASE)
        if match:
            day = int(match.group(1))
            month_str = match.group(2)
            if month_str:
                months = {"jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
                         "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12}
                month = months.get(month_str.lower(), today.month)
                try:
                    return date(today.year, month, day)
                except ValueError:
                    pass

        return None  # Default to today (handled by caller)

    def _extract_time_range(self, text: str) -> str | None:
        """Extract time range for queries."""
        for range_name, pattern in self.TIME_PATTERNS.items():
            if re.search(pattern, text, re.IGNORECASE):
                return range_name
        return None

    def _extract_split_info(self, text: str) -> tuple[int | None, list[str] | None]:
        """Extract split payment information."""
        # "split with 4 people"
        match = re.search(r"(?:split|divide)\s*(?:with|among|between)?\s*(\d+)\s*people", text, re.IGNORECASE)
        if match:
            return int(match.group(1)), None

        # "with Rahul and Priya"
        match = re.search(r"with\s+([A-Z][a-z]+(?:\s*(?:,|and)\s*[A-Z][a-z]+)*)", text)
        if match:
            people_str = match.group(1)
            people = re.split(r"\s*(?:,|and)\s*", people_str)
            return len(people) + 1, people  # +1 for the user

        return None, None

    def _extract_person_name(self, text: str) -> str | None:
        """Extract a person's name from text."""
        # "Rahul paid me back"
        match = re.search(r"([A-Z][a-z]+)\s+(?:paid|settled|cleared)", text)
        if match:
            return match.group(1)

        # "received from Rahul"
        match = re.search(r"(?:from|by)\s+([A-Z][a-z]+)", text)
        if match:
            return match.group(1)

        return None
