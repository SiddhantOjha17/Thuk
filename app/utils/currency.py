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

# Number with optional k/K suffix (e.g. 2.5k, 10K)
_NUM = r"(\d+(?:,\d{3})*(?:\.\d{1,2})?)([kK])?"

# Regex patterns for amount extraction — each group 1 is the digits, group 2 is the k suffix
AMOUNT_PATTERNS = [
    # ₹500, ₹2.5k, $100k
    r"[₹$€£¥]\s*" + _NUM,
    # 500₹, 2.5k$
    _NUM + r"\s*[₹$€£¥]",
    # Rs 500, Rs. 2k, INR 500
    r"(?:rs\.?|inr|usd|eur|gbp|aed)\s*" + _NUM,
    # 500 Rs, 2.5k rupees
    _NUM + r"\s*(?:rs\.?|rupees?|dollars?|euros?|pounds?|dirhams?)",
    # Plain number with optional k: 500, 2.5k, 10K
    _NUM,
]


def detect_currency(text: str) -> str:
    """Detect currency from text, defaults to INR."""
    text_lower = text.lower()

    # Check for currency symbols first (single-char, no word boundary needed)
    for symbol in ["₹", "$", "€", "£", "¥"]:
        if symbol in text:
            return CURRENCY_SYMBOLS[symbol]

    # Check for currency words using whole-word matching to avoid false positives
    # e.g. "rs" must not match inside "dollars"
    for word, code in CURRENCY_SYMBOLS.items():
        if len(word) <= 1:
            continue  # symbols already handled above
        if re.search(r"\b" + re.escape(word) + r"\b", text_lower):
            return code

    return "INR"


def parse_amount(text: str) -> Decimal | None:
    """Extract amount from text, handling k/K shorthand (e.g. 2.5k → 2500)."""
    for pattern in AMOUNT_PATTERNS:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            amount_str = match.group(1).replace(",", "")
            suffix = match.group(2) if match.lastindex and match.lastindex >= 2 else None
            try:
                value = Decimal(amount_str)
                if suffix and suffix.lower() == "k":
                    value *= 1000
                return value
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
