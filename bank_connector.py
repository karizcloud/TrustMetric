"""
bank_connector.py
-----------------
Simulated bank transaction connector.

Mimics a real bank API integration by loading pre-defined user datasets
from the bank_data/ directory.  In production this module would be swapped
out for a live Open Banking / Account Aggregator API call — the rest of the
application (main.py, trust_score_engine.py) stays unchanged.

Supported user IDs:  good_user  |  average_user  |  risky_user
"""

from __future__ import annotations

import json
from pathlib import Path

# Directory that holds the simulated bank datasets
BANK_DATA_DIR = Path(__file__).parent / "bank_data"

# Registry of known user IDs — makes available users discoverable via the API
KNOWN_USERS: list[str] = [
    p.stem for p in sorted(BANK_DATA_DIR.glob("*.json"))
]


class BankConnectionError(Exception):
    """Raised when the connector cannot retrieve data for a user."""


def fetch_bank_transactions(user_id: str) -> dict:
    """
    Simulate fetching a user's full financial dataset from a bank.

    Parameters
    ----------
    user_id : str
        Identifier for the bank customer.
        Maps directly to a JSON file in bank_data/<user_id>.json

    Returns
    -------
    dict
        Full financial dataset in the format expected by calculate_trust_score().

    Raises
    ------
    BankConnectionError
        If the user_id does not match any known dataset.
    """
    dataset_path = BANK_DATA_DIR / f"{user_id}.json"

    if not dataset_path.exists():
        raise BankConnectionError(
            f"No bank data found for user '{user_id}'. "
            f"Available users: {KNOWN_USERS}"
        )

    with dataset_path.open("r", encoding="utf-8") as fh:
        data = json.load(fh)

    return data