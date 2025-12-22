"""Currency detection and parsing utilities."""

import re
from decimal import Decimal, InvalidOperation

# Currency symbol to code mapping
CURRENCY_SYMBOLS: dict[str, str] = {
    "₹": "INR",
    "rs": "INR",
    "rs.": "INR",
    "inr": "INR",
    "rupees": "INR",
    "rupee": "INR",
    "$": "USD",
    "usd": "USD",
    "dollars": "USD",
    "dollar": "USD",
    "€": "EUR",
    "eur": "EUR",
    "euros": "EUR",
    "euro": "EUR",
    "£": "GBP",
    "gbp": "GBP",
    "pounds": "GBP",
    "pound": "GBP",
    "¥": "JPY",
    "jpy": "JPY",
    "yen": "JPY",
    "aed": "AED",
    "dirhams": "AED",
    "dirham": "AED",
}

# Regex patterns for amount extraction
AMOUNT_PATTERNS = [
    # ₹500, $100, €50, £30
    r"[₹$€£¥]\s*(\d+(?:,\d{3})*(?:\.\d{1,2})?)",
    # 500₹, 100$
    r"(\d+(?:,\d{3})*(?:\.\d{1,2})?)\s*[₹$€£¥]",
    # Rs 500, Rs. 500, INR 500
    r"(?:rs\.?|inr|usd|eur|gbp|aed)\s*(\d+(?:,\d{3})*(?:\.\d{1,2})?)",
    # 500 Rs, 500 rupees
    r"(\d+(?:,\d{3})*(?:\.\d{1,2})?)\s*(?:rs\.?|rupees?|dollars?|euros?|pounds?|dirhams?)",
    # Just numbers (fallback)
    r"(\d+(?:,\d{3})*(?:\.\d{1,2})?)",
]


def detect_currency(text: str) -> str:
    """Detect currency from text, defaults to INR."""
    text_lower = text.lower()

    # Check for currency symbols first
    for symbol in ["₹", "$", "€", "£", "¥"]:
        if symbol in text:
            return CURRENCY_SYMBOLS[symbol]

    # Check for currency words
    for word, code in CURRENCY_SYMBOLS.items():
        if word in text_lower:
            return code

    # Default to INR
    return "INR"


def parse_amount(text: str) -> Decimal | None:
    """Extract amount from text."""
    for pattern in AMOUNT_PATTERNS:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            amount_str = match.group(1)
            # Remove commas
            amount_str = amount_str.replace(",", "")
            try:
                return Decimal(amount_str)
            except InvalidOperation:
                continue
    return None


def format_amount(amount: Decimal, currency: str = "INR") -> str:
    """Format amount with currency symbol."""
    symbol_map = {
        "INR": "₹",
        "USD": "$",
        "EUR": "€",
        "GBP": "£",
        "JPY": "¥",
        "AED": "AED ",
    }
    symbol = symbol_map.get(currency, currency + " ")

    # Format with commas for Indian numbering if INR
    if currency == "INR":
        # Indian number system: 1,00,000 format
        amount_int = int(amount)
        amount_str = str(amount_int)
        if len(amount_str) > 3:
            last_three = amount_str[-3:]
            remaining = amount_str[:-3]
            formatted = []
            while len(remaining) > 2:
                formatted.insert(0, remaining[-2:])
                remaining = remaining[:-2]
            if remaining:
                formatted.insert(0, remaining)
            amount_str = ",".join(formatted) + "," + last_three
        return f"{symbol}{amount_str}"
    else:
        return f"{symbol}{amount:,.2f}"
