"""
trust_score_engine.py
---------------------
Alternative Financial Trust Score Engine
Computes a transparent, rule-based trust score (300–900) for individuals
without traditional credit histories.

Author: Senior Backend Engineer — Fintech Hackathon
"""

import json
import statistics
from typing import Any

from transaction_cleaner import normalize_transactions


# ---------------------------------------------------------------------------
# STEP 1 — DATA PREPROCESSING
# ---------------------------------------------------------------------------

def preprocess_transactions(data: dict) -> dict:
    """
    Compute aggregate spending indicators from raw transaction list.

    Returns a dict with:
        - total_monthly_expense
        - total_investment_spending
        - total_lifestyle_spending
    """
    transactions = data.get("transactions", [])

    total_monthly_expense = 0.0
    total_investment_spending = 0.0
    total_lifestyle_spending = 0.0

    for txn in transactions:
        amount = float(txn.get("amount", 0))
        category = txn.get("category", "").lower()

        if category == "income":
            continue  # Exclude income transactions from expense totals

        total_monthly_expense += amount

        if category == "investment":
            total_investment_spending += amount
        elif category == "lifestyle":
            total_lifestyle_spending += amount

    return {
        "total_monthly_expense": total_monthly_expense,
        "total_investment_spending": total_investment_spending,
        "total_lifestyle_spending": total_lifestyle_spending,
    }


# ---------------------------------------------------------------------------
# STEP 2 — FEATURE CALCULATIONS
# ---------------------------------------------------------------------------

def calculate_liquidity_score(monthly_income: float, total_monthly_expense: float) -> float:
    """
    Measures ability to repay loans based on income vs. expenses.
    Score range: 0–100.
    """
    if total_monthly_expense == 0:
        return 90.0  # No expenses → fully liquid

    ratio = monthly_income / total_monthly_expense

    if ratio < 1.0:
        return 20.0
    elif ratio < 1.5:
        return 50.0
    elif ratio < 2.0:
        return 70.0
    else:
        return 90.0


def calculate_discipline_score(bill_payment_history: dict) -> float:
    """
    Measures reliability in paying recurring obligations.
    Score range: 0–100.
    """
    total_bills = bill_payment_history.get("total_bills", 0)
    bills_paid_on_time = bill_payment_history.get("bills_paid_on_time", 0)

    if total_bills == 0:
        return 50.0  # Neutral score when no bill history exists

    discipline_ratio = bills_paid_on_time / total_bills
    return round(discipline_ratio * 100, 2)


EXPENSE_CATEGORIES = {"utility", "grocery", "lifestyle", "rent"}


def calculate_stability_score(transactions: list[dict]) -> float:
    """
    Measures spending stability via standard deviation of pure expense amounts.
    Lower volatility → higher stability score.
    Score range: 0–100.

    Only expense categories are included: utility, grocery, lifestyle, rent.
    Income and investment transactions are explicitly excluded — income would
    inflate volatility artificially, and investments represent planned behavior
    that should not penalise the stability score.
    """
    amounts = [
        float(txn["amount"])
        for txn in transactions
        if txn.get("category", "").lower() in EXPENSE_CATEGORIES
    ]

    if len(amounts) < 2:
        return 50.0  # Insufficient data → neutral score

    std_dev = statistics.stdev(amounts)
    mean = statistics.mean(amounts)

    # Coefficient of Variation (CV) — normalized volatility
    if mean == 0:
        return 50.0

    cv = std_dev / mean

    # Map CV to a 0–100 score: CV=0 → 100, CV≥2 → 0
    raw_score = max(0.0, 100.0 - (cv * 50.0))
    return round(min(raw_score, 100.0), 2)


def calculate_investment_score(
    total_investment_spending: float, total_monthly_expense: float
) -> float:
    """
    Measures long-term wealth-building behavior.
    Score range: 0–100.
    """
    if total_monthly_expense == 0:
        return 0.0

    investment_ratio = total_investment_spending / total_monthly_expense

    if investment_ratio < 0.05:
        return 20.0   # Low
    elif investment_ratio < 0.15:
        return 60.0   # Medium
    else:
        return 90.0   # High


def calculate_emergency_fund_score(
    emergency_savings: float, total_monthly_expense: float
) -> float:
    """
    Measures financial safety buffer in months of expense coverage.
    Score range: 0–100.
    """
    if total_monthly_expense == 0:
        return 90.0  # No expenses → fully covered

    coverage = emergency_savings / total_monthly_expense

    if coverage < 1.0:
        return 30.0
    elif coverage < 3.0:
        return 60.0
    else:
        return 90.0


def calculate_insurance_score(insurance: dict) -> float:
    """
    Measures protection against financial shocks via insurance coverage.
    Score range: 0–100.
    """
    score = 0.0

    if insurance.get("has_health_insurance", False):
        score += 50.0
    if insurance.get("has_life_insurance", False):
        score += 30.0
    if insurance.get("has_vehicle_insurance", False):
        score += 20.0

    return min(score, 100.0)


def calculate_asset_protection_score(
    investment_score: float,
    emergency_fund_score: float,
    insurance_score: float,
) -> float:
    """
    Combines long-term financial safety indicators.
    Score range: 0–100.
    """
    score = (
        0.40 * investment_score
        + 0.35 * emergency_fund_score
        + 0.25 * insurance_score
    )
    return round(score, 2)


def calculate_risk_score(
    total_lifestyle_spending: float, total_monthly_expense: float
) -> float:
    """
    Measures risky discretionary spending behavior.
    Higher lifestyle ratio → lower risk score.
    Score range: 0–100.
    """
    if total_monthly_expense == 0:
        return 100.0

    lifestyle_ratio = total_lifestyle_spending / total_monthly_expense
    raw_score = 100.0 - (lifestyle_ratio * 100.0)
    return round(max(0.0, min(raw_score, 100.0)), 2)


# ---------------------------------------------------------------------------
# STEP 3–5 — TRUST SCORE, NORMALIZATION & TIER CLASSIFICATION
# ---------------------------------------------------------------------------

def calculate_trust_score(data: dict) -> dict[str, Any]:
    """
    Master function. Accepts a user financial dataset and returns:
        - trust_score (300–900)
        - risk_tier
        - score_breakdown (per dimension, 0–100)
    """
    # --- Preprocessing ---
    # Normalize raw descriptions / missing merchants before any scoring logic
    if "transactions" in data:
        data = {**data, "transactions": normalize_transactions(data["transactions"])}

    aggregates = preprocess_transactions(data)
    total_monthly_expense = aggregates["total_monthly_expense"]
    total_investment_spending = aggregates["total_investment_spending"]
    total_lifestyle_spending = aggregates["total_lifestyle_spending"]

    monthly_income = float(data.get("monthly_income", 0))
    transactions = data.get("transactions", [])
    bill_payment_history = data.get("bill_payment_history", {})
    emergency_savings = float(data.get("emergency_savings", 0))
    insurance = data.get("insurance", {})

    # --- Individual Scores ---
    liquidity = calculate_liquidity_score(monthly_income, total_monthly_expense)
    discipline = calculate_discipline_score(bill_payment_history)
    stability = calculate_stability_score(transactions)
    investment = calculate_investment_score(total_investment_spending, total_monthly_expense)
    emergency_fund = calculate_emergency_fund_score(emergency_savings, total_monthly_expense)
    insurance_sc = calculate_insurance_score(insurance)
    asset_protection = calculate_asset_protection_score(investment, emergency_fund, insurance_sc)
    risk = calculate_risk_score(total_lifestyle_spending, total_monthly_expense)

    # --- Raw Trust Score (0–100) ---
    trust_score_raw = (
        0.25 * liquidity
        + 0.25 * discipline
        + 0.20 * stability
        + 0.15 * asset_protection
        + 0.15 * risk
    )

    # --- Normalize to 300–900 ---
    final_score = round(300 + (trust_score_raw / 100) * 600)

    # --- Risk Tier ---
    risk_tier = classify_risk_tier(final_score)

    return {
        "trust_score": final_score,
        "risk_tier": risk_tier,
        "score_breakdown": {
            "liquidity": round(liquidity, 2),
            "discipline": round(discipline, 2),
            "stability": round(stability, 2),
            "asset_protection": round(asset_protection, 2),
            "risk": round(risk, 2),
        },
    }


def classify_risk_tier(score: int) -> str:
    """Maps a final trust score (300–900) to a human-readable risk tier."""
    if score >= 820:
        return "Excellent"
    elif score >= 740:
        return "Low Risk"
    elif score >= 650:
        return "Moderate Risk"
    elif score >= 550:
        return "High Risk"
    else:
        return "Very High Risk"


# ---------------------------------------------------------------------------
# SAMPLE DATASET & ENTRY POINT
# ---------------------------------------------------------------------------

SAMPLE_DATA = {
    "monthly_income": 85000,
    "transactions": [
        {"date": "2024-01-02", "merchant": "Salary",        "amount": 85000, "category": "income"},
        {"date": "2024-01-05", "merchant": "City Electric",  "amount": 2200,  "category": "utility"},
        {"date": "2024-01-07", "merchant": "D-Mart",         "amount": 5800,  "category": "grocery"},
        {"date": "2024-01-10", "merchant": "Zomato",         "amount": 3200,  "category": "lifestyle"},
        {"date": "2024-01-12", "merchant": "Zerodha SIP",    "amount": 10000, "category": "investment"},
        {"date": "2024-01-15", "merchant": "House Rent",     "amount": 18000, "category": "rent"},
        {"date": "2024-01-17", "merchant": "Netflix",        "amount": 649,   "category": "lifestyle"},
        {"date": "2024-01-20", "merchant": "Reliance Fresh",  "amount": 3100,  "category": "grocery"},
        {"date": "2024-01-22", "merchant": "LIC Premium",    "amount": 4500,  "category": "investment"},
        {"date": "2024-01-25", "merchant": "Amazon Shopping", "amount": 2800, "category": "lifestyle"},
        {"date": "2024-01-28", "merchant": "Airtel Bill",    "amount": 999,   "category": "utility"},
        {"date": "2024-01-30", "merchant": "Gold SGB",       "amount": 5000,  "category": "investment"},
    ],
    "bill_payment_history": {
        "total_bills": 24,
        "bills_paid_on_time": 22,
    },
    "emergency_savings": 150000,
    "insurance": {
        "has_health_insurance": True,
        "has_life_insurance": True,
        "has_vehicle_insurance": False,
    },
}


if __name__ == "__main__":
    result = calculate_trust_score(SAMPLE_DATA)
    print("=" * 50)
    print("  ALTERNATIVE FINANCIAL TRUST SCORE REPORT")
    print("=" * 50)
    print(json.dumps(result, indent=2))
    print("=" * 50)