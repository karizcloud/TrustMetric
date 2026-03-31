"""
loan_engine.py
--------------
Micro-Loan Eligibility Engine — v2.

Replaces the previous band-based approach with a cash-flow driven formula
that uses actual surplus income, making recommendations proportional to what
the user can genuinely afford to repay.

Formula (Step 5 spec)
---------------------
    surplus            = monthly_income - total_expenses
    repayment_capacity = surplus * 0.4
    risk_factor        = trust_score / 900
    recommended_loan   = repayment_capacity * risk_factor * 12

Clamped to ₹5,000 – ₹50,000.

Repayment reliability
---------------------
Weighted combination of three behavioural dimensions:
    reliability = (trust_score_pct * 0.5) + (discipline * 0.3) + (stability * 0.2)
Clamped to 50%–95%.

The loan range returned is the fixed tier band the trust score maps into,
giving users context for where they sit regardless of their income.

Public API
----------
    calculate_loan_eligibility(
        trust_score, monthly_income, total_expenses,
        stability_score, discipline_score
    ) -> dict
"""

from __future__ import annotations


# ---------------------------------------------------------------------------
# LOAN TIER BANDS  (for context display — not used in recommended calculation)
# ---------------------------------------------------------------------------

_LOAN_BANDS: list[tuple[int, list[int]]] = [
    (750, [35_000, 50_000]),
    (650, [20_000, 35_000]),
    (500, [10_000, 20_000]),
    (300, [ 5_000, 10_000]),
]

_LOAN_MIN =  5_000
_LOAN_MAX = 50_000

_RELIABILITY_MIN = 50.0
_RELIABILITY_MAX = 95.0


# ---------------------------------------------------------------------------
# INTERNAL HELPERS
# ---------------------------------------------------------------------------

def _get_loan_range(trust_score: int) -> list[int]:
    """Map trust score to its contextual [min, max] tier band."""
    for threshold, band in _LOAN_BANDS:
        if trust_score >= threshold:
            return band
    return _LOAN_BANDS[-1][1]


def _calculate_recommended_loan(
    trust_score:    int,
    monthly_income: float,
    total_expenses: float,
) -> int:
    """
    Cash-flow driven loan recommendation.

        surplus            = monthly_income - total_expenses
        repayment_capacity = surplus * 0.4
        risk_factor        = trust_score / 900
        recommended_loan   = repayment_capacity * risk_factor * 12

    Clamped to [₹5,000, ₹50,000] and rounded to nearest ₹500.
    """
    surplus            = max(monthly_income - total_expenses, 0.0)
    repayment_capacity = surplus * 0.4
    risk_factor        = trust_score / 900
    raw                = repayment_capacity * risk_factor * 12

    # Clamp then round to nearest ₹500 for a cleaner UX
    clamped = max(_LOAN_MIN, min(_LOAN_MAX, raw))
    rounded = round(clamped / 500) * 500
    return int(max(rounded, _LOAN_MIN))


def _calculate_repayment_reliability(
    trust_score:     int,
    discipline_score: float,
    stability_score:  float,
) -> float:
    """
    Weighted reliability score using three behavioural dimensions.

        trust_pct   = (trust_score - 300) / 6   → maps 300–900 to 0–100
        reliability = trust_pct*0.5 + discipline*0.3 + stability*0.2

    Clamped to [50%, 95%].
    """
    trust_pct = (trust_score - 300) / 6          # 0–100
    raw = (
        trust_pct        * 0.50
        + discipline_score * 0.30
        + stability_score  * 0.20
    )
    return round(max(_RELIABILITY_MIN, min(_RELIABILITY_MAX, raw)), 2)


# ---------------------------------------------------------------------------
# PUBLIC API
# ---------------------------------------------------------------------------

def calculate_loan_eligibility(
    trust_score:      int,
    monthly_income:   float,
    total_expenses:   float   = 0.0,
    stability_score:  float   = 50.0,
    discipline_score: float   = 50.0,
) -> dict:
    """
    Calculate micro-loan eligibility using the cash-flow driven formula.

    Parameters
    ----------
    trust_score      : int    — overall trust score (300–900)
    monthly_income   : float  — gross monthly income in INR
    total_expenses   : float  — total monthly non-income spending in INR
    stability_score  : float  — spending stability dimension (0–100)
    discipline_score : float  — bill payment discipline dimension (0–100)

    Returns
    -------
    dict
        {
            "recommended_loan":      int,         # INR, clamped ₹5k–₹50k
            "loan_range":            [int, int],  # contextual tier band
            "repayment_reliability": float,       # % (50–95)
        }

    Notes
    -----
    total_expenses defaults to 0.0 for backward compatibility — callers that
    only pass trust_score and monthly_income still get a valid (conservative)
    result instead of a TypeError.
    """
    recommended = _calculate_recommended_loan(trust_score, monthly_income, total_expenses)
    loan_range  = _get_loan_range(trust_score)
    reliability = _calculate_repayment_reliability(trust_score, discipline_score, stability_score)

    return {
        "recommended_loan":      recommended,
        "loan_range":            loan_range,
        "repayment_reliability": reliability,
    }