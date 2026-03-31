"""
transaction_cleaner.py
----------------------
Transaction Normalization Layer.

Cleans raw bank transaction descriptions (UPI strings, POS entries, NEFT
narrations, etc.) into a normalized merchant name and, optionally, infers
a spending category when none is supplied.

Designed as a pure pre-processing step — it has no dependency on the
scoring engine and can be tested independently.
"""

from __future__ import annotations

import re


# ---------------------------------------------------------------------------
# PAYMENT PREFIX / NOISE PATTERNS
# Ordered from most-specific to least-specific so that longer matches are
# stripped before shorter ones.
# ---------------------------------------------------------------------------

# Payment channel prefixes that precede the actual merchant name
_CHANNEL_PREFIXES: list[str] = [
    r"upi/",          # UPI/NETFLIX-SUB
    r"upi-",          # UPI-ZOMATO-12345
    r"upi\s+",        # UPI SWIGGY
    r"pos\s+txn\s+",  # POS TXN DMART MUMBAI
    r"pos\s+",        # POS AMAZON
    r"card\s+swipe\s+",
    r"card\s+",
    r"neft\s+",
    r"imps\s+",
    r"rtgs\s+",
    r"nach\s+",
    r"ecs\s+",
    r"ach\s+",
    r"txn\s+",
    r"payment\s+",
    r"transfer\s+",
    r"purchase\s+",
    r"debit\s+",
]

# Noise suffixes / trailing location / reference tokens to discard
_NOISE_SUFFIXES: list[str] = [
    r"\s+mumbai.*$",
    r"\s+delhi.*$",
    r"\s+bangalore.*$",
    r"\s+chennai.*$",
    r"\s+hyderabad.*$",
    r"\s+pune.*$",
    r"\s+india.*$",
    r"\s+subscription.*$",
    r"\s+monthly.*$",
    r"\s+auto.*$",
    r"\s+pay$",          # "AMAZON PAY" → "amazon"
    r"\s+ltd.*$",
    r"\s+pvt.*$",
    r"\s+inc.*$",
]

# Known generic words that are never a merchant name
_STOP_WORDS: set[str] = {
    "to", "from", "by", "at", "the", "and", "for", "of",
    "ref", "no", "id", "via", "a", "an",
}

# ---------------------------------------------------------------------------
# MERCHANT → CATEGORY LOOKUP
# Extend this dictionary to support new merchants without touching any logic.
# ---------------------------------------------------------------------------

MERCHANT_CATEGORY_MAP: dict[str, str] = {
    # Income
    "salary": "income",
    "payroll": "income",
    "stipend": "income",
    "freelance": "income",
    "dividend": "income",

    # Utilities
    "electricity": "utility",
    "mseb":        "utility",
    "best":        "utility",
    "airtel":      "utility",
    "jio":         "utility",
    "bsnl":        "utility",
    "vodafone":    "utility",
    "vi":          "utility",
    "water":       "utility",
    "gas":         "utility",
    "broadband":   "utility",
    "tata":        "utility",
    "nmmc":        "utility",

    # Grocery
    "dmart":       "grocery",
    "bigbasket":   "grocery",
    "big basket":  "grocery",
    "zepto":       "grocery",
    "blinkit":     "grocery",
    "grofers":     "grocery",
    "nature":      "grocery",
    "reliance fresh": "grocery",
    "reliance":    "grocery",
    "more":        "grocery",
    "spencer":     "grocery",
    "kirana":      "grocery",
    "vegetable":   "grocery",

    # Lifestyle
    "zomato":      "lifestyle",
    "swiggy":      "lifestyle",
    "netflix":     "lifestyle",
    "hotstar":     "lifestyle",
    "disney":      "lifestyle",
    "spotify":     "lifestyle",
    "amazon":      "lifestyle",
    "flipkart":    "lifestyle",
    "myntra":      "lifestyle",
    "ajio":        "lifestyle",
    "nykaa":       "lifestyle",
    "meesho":      "lifestyle",
    "bookmyshow":  "lifestyle",
    "uber":        "lifestyle",
    "ola":         "lifestyle",
    "rapido":      "lifestyle",
    "gym":         "lifestyle",
    "cult":        "lifestyle",
    "gaming":      "lifestyle",
    "pub":         "lifestyle",
    "bar":         "lifestyle",
    "fashion":     "lifestyle",
    "food":        "lifestyle",
    "delivery":    "lifestyle",

    # Investment
    "zerodha":     "investment",
    "groww":       "investment",
    "upstox":      "investment",
    "lic":         "investment",
    "sip":         "investment",
    "mutual fund": "investment",
    "nps":         "investment",
    "ppf":         "investment",
    "sgb":         "investment",
    "gold":        "investment",
    "hdfc amc":    "investment",

    # Rent
    "rent":        "rent",
    "pg":          "rent",
    "hostel":      "rent",
    "accommodation": "rent",
    "housing":     "rent",
    "landlord":    "rent",
    "nobroker":    "rent",
    "nestaway":    "rent",
}


# ---------------------------------------------------------------------------
# CORE CLEANING FUNCTION
# ---------------------------------------------------------------------------

def clean_transaction_description(description: str) -> str:
    """
    Normalize a raw bank transaction description to a clean merchant keyword.

    Steps
    -----
    1. Lowercase
    2. Strip payment channel prefixes  (upi-, pos txn, neft, card, …)
    3. Remove digits and special characters
    4. Strip noise suffixes             (city names, "pay", "subscription", …)
    5. Remove stop words from multi-token results
    6. Return the first meaningful token as the merchant name

    Parameters
    ----------
    description : str
        Raw transaction string from a bank statement.

    Returns
    -------
    str
        Normalized merchant keyword (lowercase, no punctuation).
        Returns "unknown" if extraction fails.

    Examples
    --------
    >>> clean_transaction_description("UPI-ZOMATO-12345")
    'zomato'
    >>> clean_transaction_description("POS TXN DMART MUMBAI")
    'dmart'
    >>> clean_transaction_description("UPI/NETFLIX-SUBSCRIPTION")
    'netflix'
    >>> clean_transaction_description("CARD AMAZON PAY")
    'amazon'
    >>> clean_transaction_description("NEFT SALARY ABC TECH")
    'salary'
    """
    if not description or not isinstance(description, str):
        return "unknown"

    text = description.lower().strip()

    # Step 1 — strip channel prefixes
    for prefix in _CHANNEL_PREFIXES:
        text = re.sub(r"^" + prefix, "", text)

    # Step 2 — replace hyphens/slashes used as separators with spaces
    text = re.sub(r"[-/]", " ", text)

    # Step 3 — remove digits and special characters (keep letters and spaces)
    text = re.sub(r"[^a-z\s]", "", text)

    # Step 4 — collapse multiple spaces
    text = re.sub(r"\s+", " ", text).strip()

    # Step 5 — strip noise suffixes
    for suffix in _NOISE_SUFFIXES:
        text = re.sub(suffix, "", text).strip()

    # Step 6 — remove stop words and take the first meaningful token
    tokens = [t for t in text.split() if t not in _STOP_WORDS and len(t) > 1]

    if not tokens:
        return "unknown"

    return tokens[0]


# ---------------------------------------------------------------------------
# CATEGORY INFERENCE
# ---------------------------------------------------------------------------

def infer_category(merchant: str) -> str:
    """
    Map a cleaned merchant name to a transaction category.

    Checks for exact match first, then falls back to substring matching
    so that compound names like "zerodha sip" still resolve correctly.

    Returns "lifestyle" as a safe default for unknown merchants.
    """
    merchant_lower = merchant.lower().strip()

    # Exact match
    if merchant_lower in MERCHANT_CATEGORY_MAP:
        return MERCHANT_CATEGORY_MAP[merchant_lower]

    # Substring match — iterate longest keys first to avoid partial collisions
    for key in sorted(MERCHANT_CATEGORY_MAP, key=len, reverse=True):
        if key in merchant_lower:
            return MERCHANT_CATEGORY_MAP[key]

    return "lifestyle"   # safe default for unrecognised merchants


# ---------------------------------------------------------------------------
# PIPELINE ENTRY POINT
# ---------------------------------------------------------------------------

def normalize_transaction(txn: dict) -> dict:
    """
    Normalize a single transaction dict in-place.

    Rules
    -----
    - If ``merchant`` is missing or blank → extract from ``description``
    - If ``category`` is missing or blank → infer from resolved merchant name
    - The original transaction dict is NOT mutated; a new dict is returned.

    Parameters
    ----------
    txn : dict
        Raw transaction with optional ``description``, ``merchant``, ``category``.

    Returns
    -------
    dict
        Cleaned transaction guaranteed to have ``merchant`` and ``category``.
    """
    cleaned = dict(txn)  # shallow copy — never mutate caller's data

    # --- Resolve merchant ---
    merchant = cleaned.get("merchant", "").strip()
    if not merchant:
        description = cleaned.get("description", "")
        merchant = clean_transaction_description(description)
    cleaned["merchant"] = merchant

    # --- Resolve category ---
    category = cleaned.get("category", "").strip()
    if not category:
        category = infer_category(merchant)
    cleaned["category"] = category

    return cleaned


def normalize_transactions(transactions: list[dict]) -> list[dict]:
    """
    Normalize an entire list of transactions.
    Passes each transaction through normalize_transaction().
    """
    return [normalize_transaction(txn) for txn in transactions]