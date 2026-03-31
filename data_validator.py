"""
data_validator.py
-----------------
Financial Profile Validation & Confidence Engine.

Analyses the raw user data and the calculated score result to:
  1. Detect data quality issues (insufficient history)
  2. Flag suspiciously perfect financial profiles (possible fabricated data)
  3. Calculate a confidence level for the trust score based on transaction volume

This module never modifies the trust score — it only appends warning messages
and returns a confidence rating so downstream consumers can calibrate trust.

Public API
----------
    validate_financial_profile(user_data, score_result)
        → { "warnings": list[str], "confidence_level": str }
"""

from __future__ import annotations


# ---------------------------------------------------------------------------
# CONFIGURATION — thresholds in one place for easy tuning
# ---------------------------------------------------------------------------

# Minimum transactions needed for a reliable score
MIN_TRANSACTIONS_WARN   = 10

# Confidence level transaction count bands
CONFIDENCE_HIGH_THRESHOLD   = 50
CONFIDENCE_MEDIUM_THRESHOLD = 20

# "Suspiciously ideal" detection — how many dimensions must exceed their
# extreme threshold before we flag the profile
IDEAL_DIMENSIONS_REQUIRED = 3

# Per-dimension extreme thresholds
EXTREME_THRESHOLDS: dict[str, float] = {
    "discipline":       95.0,
    "liquidity":        90.0,
    "risk":             90.0,
    "asset_protection": 90.0,
}


# ---------------------------------------------------------------------------
# CHECK 1 — Insufficient transaction history
# ---------------------------------------------------------------------------

def _check_insufficient_data(transactions: list) -> list[str]:
    """
    Warn when the transaction list is too small to produce a reliable score.
    The scoring engine can calculate a number from even 2 transactions, but
    the result will be highly sensitive to individual amounts.
    """
    warnings = []
    count = len(transactions)

    if count < MIN_TRANSACTIONS_WARN:
        warnings.append(
            f"Insufficient transaction history ({count} transaction"
            f"{'s' if count != 1 else ''} provided). "
            "Score reliability is low — at least 10 transactions are recommended."
        )

    return warnings


# ---------------------------------------------------------------------------
# CHECK 2 — Suspiciously ideal financial profile
# ---------------------------------------------------------------------------

def _check_ideal_profile(score_breakdown: dict) -> list[str]:
    """
    Detect financial profiles where an improbable number of dimensions are
    simultaneously near-perfect.  This can indicate:
      • fabricated or manually curated test data
      • an input error (e.g. all amounts set to the same value)
      • a genuinely exceptional user (which is fine — we only warn, not penalise)

    The check counts how many tracked dimensions exceed their extreme threshold.
    If IDEAL_DIMENSIONS_REQUIRED or more exceed their thresholds, a warning is
    added.  The trust score is never changed.
    """
    warnings = []
    triggered: list[str] = []

    for dimension, threshold in EXTREME_THRESHOLDS.items():
        actual = score_breakdown.get(dimension, 0.0)
        if actual > threshold:
            triggered.append(f"{dimension} ({actual:.1f} > {threshold})")

    if len(triggered) >= IDEAL_DIMENSIONS_REQUIRED:
        warnings.append(
            "Financial profile appears unusually ideal — "
            f"{len(triggered)} score dimensions exceed extreme thresholds "
            f"({', '.join(triggered)}). Please verify the uploaded data."
        )

    return warnings


# ---------------------------------------------------------------------------
# CONFIDENCE LEVEL — based on transaction volume
# ---------------------------------------------------------------------------

def _calculate_confidence_level(transactions: list) -> str:
    """
    Derive a confidence level string from the number of transactions.

    More data points → less sensitivity to individual outliers → higher
    confidence that the score reflects actual long-term financial behaviour.

    Returns
    -------
    str
        "High"   — 50+ transactions
        "Medium" — 20–49 transactions
        "Low"    — fewer than 20 transactions
    """
    count = len(transactions)

    if count >= CONFIDENCE_HIGH_THRESHOLD:
        return "High"
    elif count >= CONFIDENCE_MEDIUM_THRESHOLD:
        return "Medium"
    else:
        return "Low"


# ---------------------------------------------------------------------------
# PUBLIC API
# ---------------------------------------------------------------------------

def validate_financial_profile(user_data: dict, score_result: dict) -> dict:
    """
    Validate a user's financial profile and produce warnings + a confidence level.

    Parameters
    ----------
    user_data : dict
        The raw financial dataset passed to the scoring engine.
        Must contain a ``transactions`` list.
    score_result : dict
        Output from ``calculate_trust_score()`` — must contain
        ``score_breakdown``.

    Returns
    -------
    dict with two keys:
        ``warnings``         list[str]  — zero or more diagnostic messages
        ``confidence_level`` str        — "High" | "Medium" | "Low"

    Notes
    -----
    - This function is read-only.  It never modifies ``user_data`` or
      ``score_result``.
    - Warnings are informational only.  Callers must not suppress scores
      based on their presence alone.
    """
    transactions    = user_data.get("transactions", [])
    score_breakdown = score_result.get("score_breakdown", {})

    warnings: list[str] = []
    warnings += _check_insufficient_data(transactions)
    warnings += _check_ideal_profile(score_breakdown)

    confidence_level = _calculate_confidence_level(transactions)

    return {
        "warnings":         warnings,
        "confidence_level": confidence_level,
    }