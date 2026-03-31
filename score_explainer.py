"""
score_explainer.py
------------------
Rule-based Score Explanation Engine.

Converts numerical score breakdown signals into human-readable financial
insights. No ML — every insight maps to an explicit threshold rule so
the reasoning is fully transparent and auditable.
"""

from __future__ import annotations


# ---------------------------------------------------------------------------
# INDIVIDUAL DIMENSION EXPLAINERS
# ---------------------------------------------------------------------------

def _explain_discipline(score: float) -> str:
    if score > 90:
        return "Excellent bill payment discipline — all or nearly all bills paid on time."
    elif score >= 70:
        return "Good bill payment reliability with occasional missed payments."
    elif score >= 60:
        return "Inconsistent bill payments detected — reliability needs improvement."
    else:
        return "Frequent late bill payments detected, which increases financial risk."


def _explain_liquidity(score: float) -> str:
    if score > 75:
        return "Income comfortably covers monthly expenses, indicating strong repayment capacity."
    elif score >= 50:
        return "Income moderately covers expenses with limited surplus."
    elif score >= 40:
        return "Expenses are approaching income levels — limited financial headroom."
    else:
        return "Expenses are close to or exceeding income, posing a repayment risk."


def _explain_stability(score: float) -> str:
    if score > 70:
        return "Spending behavior is stable and predictable across the month."
    elif score >= 40:
        return "Moderate spending volatility detected — some irregular expense patterns."
    else:
        return "High spending volatility reduces financial stability and predictability."


def _explain_asset_protection(score: float) -> str:
    if score > 80:
        return "Strong financial protection through savings, investments, and insurance coverage."
    elif score >= 50:
        return "Moderate financial safety buffer — consider building emergency savings or investments."
    elif score >= 40:
        return "Limited financial protection — low savings, investments, or insurance coverage."
    else:
        return "Minimal financial protection detected — high vulnerability to financial shocks."


def _explain_risk(score: float) -> str:
    if score > 80:
        return "Low lifestyle spending indicates responsible and disciplined financial behavior."
    elif score >= 50:
        return "Moderate lifestyle spending detected — within acceptable range."
    elif score >= 40:
        return "Elevated discretionary spending is reducing overall financial resilience."
    else:
        return "High discretionary spending significantly increases financial risk."


def _explain_overall(trust_score: int) -> str:
    if trust_score > 740:
        return (
            f"Overall trust score of {trust_score} reflects strong financial behavior "
            "— the user is considered low risk for lending."
        )
    elif trust_score >= 650:
        return (
            f"Overall trust score of {trust_score} reflects moderate financial stability "
            "with manageable risk — some areas need attention."
        )
    else:
        return (
            f"Overall trust score of {trust_score} indicates higher credit risk "
            "— significant improvement in financial habits is recommended."
        )


# ---------------------------------------------------------------------------
# PUBLIC API
# ---------------------------------------------------------------------------

def generate_score_insights(score_result: dict) -> list[str]:
    """
    Analyze a trust score result and return a list of human-readable insights.

    Parameters
    ----------
    score_result : dict
        Output from calculate_trust_score() containing keys:
        trust_score, risk_tier, score_breakdown

    Returns
    -------
    list[str]
        Ordered list of insight messages — one per scoring dimension,
        followed by an overall summary.
    """
    breakdown = score_result.get("score_breakdown", {})
    trust_score = score_result.get("trust_score", 0)

    insights = [
        _explain_liquidity(breakdown.get("liquidity", 0)),
        _explain_discipline(breakdown.get("discipline", 0)),
        _explain_stability(breakdown.get("stability", 0)),
        _explain_asset_protection(breakdown.get("asset_protection", 0)),
        _explain_risk(breakdown.get("risk", 0)),
        _explain_overall(trust_score),
    ]

    return insights