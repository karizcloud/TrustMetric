"""
score_simulator.py
------------------
Trust Score Simulator.

Lets users test "what if" financial behaviour changes without touching real
data.  The module clones the user's dataset, applies the requested
modifications in memory, recalculates the trust score, and returns a
side-by-side comparison.

Supported simulation levers
----------------------------
reduce_lifestyle_spending_percent : float   (0–100)
    Reduces the amount of every lifestyle-category transaction by this %.

increase_investment_percent       : float   (0–100)
    Increases the amount of every investment-category transaction by this %.

Design rules
------------
- The original dataset is NEVER mutated (deep-copy before any change).
- Unknown or zero-value changes are no-ops — safe to call with partial input.
- The function returns a plain dict so it integrates cleanly with FastAPI and
  can also be called from tests without any web framework dependency.

Public API
----------
    simulate_score(current_data, simulation_changes)  ->  dict
"""

from __future__ import annotations

import copy

from trust_score_engine import calculate_trust_score


# ---------------------------------------------------------------------------
# CATEGORY CONSTANTS
# ---------------------------------------------------------------------------

_LIFESTYLE_CATEGORY  = "lifestyle"
_INVESTMENT_CATEGORY = "investment"


# ---------------------------------------------------------------------------
# INTERNAL — data mutation helpers  (operate on a deep-copied dataset)
# ---------------------------------------------------------------------------

def _apply_lifestyle_reduction(transactions: list[dict], reduction_pct: float) -> list[dict]:
    """
    Multiply every lifestyle transaction amount by (1 - reduction_pct/100).
    Non-lifestyle transactions are returned unchanged.
    """
    if reduction_pct <= 0:
        return transactions

    multiplier = 1.0 - (reduction_pct / 100.0)
    return [
        {**txn, "amount": round(txn["amount"] * multiplier, 2)}
        if txn.get("category", "").lower() == _LIFESTYLE_CATEGORY
        else txn
        for txn in transactions
    ]


def _apply_investment_increase(transactions: list[dict], increase_pct: float) -> list[dict]:
    """
    Multiply every investment transaction amount by (1 + increase_pct/100).
    Non-investment transactions are returned unchanged.
    """
    if increase_pct <= 0:
        return transactions

    multiplier = 1.0 + (increase_pct / 100.0)
    return [
        {**txn, "amount": round(txn["amount"] * multiplier, 2)}
        if txn.get("category", "").lower() == _INVESTMENT_CATEGORY
        else txn
        for txn in transactions
    ]


def _apply_changes(data: dict, changes: dict) -> dict:
    """
    Apply all simulation changes to a deep copy of *data*.
    Returns the modified copy — the original is never touched.
    """
    simulated = copy.deepcopy(data)
    transactions = simulated.get("transactions", [])

    lifestyle_reduction = float(changes.get("reduce_lifestyle_spending_percent", 0))
    investment_increase = float(changes.get("increase_investment_percent",        0))

    transactions = _apply_lifestyle_reduction(transactions, lifestyle_reduction)
    transactions = _apply_investment_increase(transactions, investment_increase)

    simulated["transactions"] = transactions
    return simulated


# ---------------------------------------------------------------------------
# PUBLIC API
# ---------------------------------------------------------------------------

def simulate_score(current_data: dict, simulation_changes: dict) -> dict:
    """
    Calculate the trust score impact of hypothetical financial behaviour changes.

    Parameters
    ----------
    current_data : dict
        The user's real financial dataset (same shape as TrustScoreRequest).
        This dict is never modified.
    simulation_changes : dict
        Keys (all optional, default 0):
            reduce_lifestyle_spending_percent  — 0–100
            increase_investment_percent        — 0–100

    Returns
    -------
    dict
        {
            "current_score":      int,    # baseline trust score
            "simulated_score":    int,    # score after applying changes
            "score_improvement":  int,    # simulated_score - current_score
            "new_risk_tier":      str,    # risk tier for the simulated score
            "simulation_insight": str,    # plain-English explanation of what changed and why
        }
    """
    # Baseline — run the engine on the unmodified data
    current_result = calculate_trust_score(current_data)
    current_score  = current_result["trust_score"]

    # Simulation — deep-copy, mutate, recalculate
    simulated_data   = _apply_changes(current_data, simulation_changes)
    simulated_result = calculate_trust_score(simulated_data)
    simulated_score  = simulated_result["trust_score"]

    insight = _generate_insight(
        current_result["score_breakdown"],
        simulated_result["score_breakdown"],
        simulation_changes,
        current_score,
        simulated_score,
    )

    return {
        "current_score":      current_score,
        "simulated_score":    simulated_score,
        "score_improvement":  simulated_score - current_score,
        "new_risk_tier":      simulated_result["risk_tier"],
        "simulation_insight": insight,
    }


# ---------------------------------------------------------------------------
# INSIGHT GENERATOR
# ---------------------------------------------------------------------------

def _generate_insight(
    before:      dict,
    after:       dict,
    changes:     dict,
    old_score:   int,
    new_score:   int,
) -> str:
    """
    Build a plain-English explanation of why the score changed.

    Approach:
      1. Identify which levers were activated (lifestyle reduction / investment increase).
      2. Calculate per-dimension deltas.
      3. Pick the dimensions that moved most and describe the causal chain.
      4. Explain the net score direction in one closing sentence.
    """
    lifestyle_pct  = float(changes.get("reduce_lifestyle_spending_percent", 0))
    investment_pct = float(changes.get("increase_investment_percent", 0))

    # Compute signed deltas for every breakdown dimension
    deltas = {k: round(after[k] - before[k], 2) for k in before}

    parts: list[str] = []

    # ── Lifestyle reduction effects ──────────────────────────────────────────
    if lifestyle_pct > 0:
        risk_delta = deltas.get("risk", 0)
        stab_delta = deltas.get("stability", 0)

        if risk_delta > 0:
            parts.append(
                f"Reducing lifestyle spending by {lifestyle_pct:.0f}% lowered "
                f"your discretionary spending ratio, improving the risk score "
                f"by {risk_delta:+.1f} points."
            )
        if stab_delta < 0:
            parts.append(
                f"However, removing lifestyle transactions changed the spending "
                f"distribution, increasing volatility and reducing the stability "
                f"score by {abs(stab_delta):.1f} points."
            )
        elif stab_delta > 0:
            parts.append(
                f"The reduced lifestyle spend also smoothed out spending patterns, "
                f"lifting the stability score by {stab_delta:+.1f} points."
            )

    # ── Investment increase effects ──────────────────────────────────────────
    if investment_pct > 0:
        ap_delta  = deltas.get("asset_protection", 0)
        liq_delta = deltas.get("liquidity", 0)

        if ap_delta > 0:
            parts.append(
                f"Increasing investment contributions by {investment_pct:.0f}% "
                f"raised the investment-to-expense ratio, boosting the asset "
                f"protection score by {ap_delta:+.1f} points."
            )
        elif ap_delta < 0:
            parts.append(
                f"Increasing investments by {investment_pct:.0f}% raised total "
                f"expenses, which reduced the asset protection score by "
                f"{abs(ap_delta):.1f} points."
            )

        if liq_delta < 0:
            parts.append(
                f"The higher expense total from larger investments also tightened "
                f"the income-to-expense ratio, pulling the liquidity score down "
                f"by {abs(liq_delta):.1f} points."
            )

    # ── Net score summary ────────────────────────────────────────────────────
    net = new_score - old_score
    if net > 0:
        parts.append(
            f"Overall, the changes produced a net gain of +{net} points "
            f"(score: {old_score} → {new_score})."
        )
    elif net < 0:
        parts.append(
            f"Overall, the competing effects resulted in a net loss of {net} points "
            f"(score: {old_score} → {new_score}). "
            f"Consider combining lifestyle reduction with investment growth for a better outcome."
        )
    else:
        parts.append(
            f"The positive and negative effects cancelled each other out, "
            f"leaving the score unchanged at {old_score}."
        )

    # ── No-op case ───────────────────────────────────────────────────────────
    if not parts:
        return "No simulation changes were applied — scores are identical."

    return " ".join(parts)