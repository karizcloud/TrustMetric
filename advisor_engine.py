"""
advisor_engine.py
-----------------
Unified Financial Advisor Engine.

Merges two previously separate modules:
  • financial_advisor.py  — rule-based improvement suggestions
  • llm_advisor.py        — Gemini AI natural-language financial advice

The module is self-contained: it loads its own environment variables from a
.env file at startup so callers never need to manage API key injection.

Setup
-----
1. Create a .env file in the project root:

       GEMINI_API_KEY=your_api_key_here

2. Install dependencies:

       pip install google-generativeai python-dotenv

Public API
----------
    generate_improvement_suggestions(score_result)  → list[str]
    generate_financial_advice(score_result, insights, suggestions)  → str
"""

from __future__ import annotations

import os
import textwrap
from pathlib import Path

from dotenv import load_dotenv

# Load .env from the project root (the directory that contains this file).
# override=False means real environment variables always take precedence over
# the .env file — useful in CI/CD or Docker deployments.
load_dotenv(dotenv_path=Path(__file__).parent / ".env", override=False)


# ===========================================================================
# SECTION 1 — RULE-BASED IMPROVEMENT SUGGESTIONS
# ===========================================================================

# ---------------------------------------------------------------------------
# Threshold constants — single source of truth, easy to tune.
# ---------------------------------------------------------------------------

_DISCIPLINE_WARN  = 70
_LIQUIDITY_WARN   = 50
_STABILITY_WARN   = 50
_ASSET_WARN       = 50
_RISK_WARN        = 60


# ---------------------------------------------------------------------------
# Per-dimension suggestion helpers (private)
# ---------------------------------------------------------------------------

def _suggest_discipline(score: float) -> list[str]:
    out = []
    if score < _DISCIPLINE_WARN:
        out.append(
            "Set up automatic bill payments or calendar reminders to improve "
            "payment consistency and raise your discipline score."
        )
    if score < 50:
        out.append(
            "Consolidate recurring bills to a single payment date to reduce "
            "the chance of missed payments."
        )
    return out


def _suggest_liquidity(score: float) -> list[str]:
    out = []
    if score < _LIQUIDITY_WARN:
        out.append(
            "Reduce non-essential monthly expenses or explore additional income "
            "sources to improve your income-to-expense ratio."
        )
    if score < 30:
        out.append(
            "Your expenses are close to or exceeding your income. Prepare a "
            "monthly budget and identify categories where spending can be cut "
            "immediately."
        )
    return out


def _suggest_stability(score: float) -> list[str]:
    out = []
    if score < _STABILITY_WARN:
        out.append(
            "Reduce large irregular spending spikes — plan major purchases in "
            "advance and spread costs across months where possible."
        )
    if score < 30:
        out.append(
            "Highly volatile spending patterns indicate inconsistent financial "
            "behavior. Consider a zero-based budgeting approach to smooth out "
            "monthly expenses."
        )
    return out


def _suggest_asset_protection(score: float) -> list[str]:
    out = []
    if score < _ASSET_WARN:
        out.append(
            "Build an emergency fund covering at least 3 months of expenses to "
            "improve your financial safety buffer."
        )
        out.append(
            "Start or increase systematic investment contributions (SIP, mutual "
            "funds, or recurring deposits) to strengthen long-term asset protection."
        )
    if score < 30:
        out.append(
            "Consider obtaining health or life insurance coverage — insurance "
            "protects against large unexpected financial shocks and directly "
            "improves your score."
        )
    return out


def _suggest_risk(score: float) -> list[str]:
    out = []
    if score < _RISK_WARN:
        out.append(
            "Reduce discretionary spending such as dining, entertainment, and "
            "online shopping to lower your financial risk profile."
        )
    if score < 40:
        out.append(
            "Lifestyle spending is significantly high relative to total expenses. "
            "Apply the 50/30/20 rule: 50% needs · 30% wants · 20% savings."
        )
    return out


def _suggest_overall(trust_score: int) -> list[str]:
    if trust_score >= 740:
        return [
            "Your overall financial health is strong. Maintain current habits "
            "and consider growing wealth through diversified investments."
        ]
    elif trust_score >= 650:
        return [
            "Address the flagged areas above to move from Moderate Risk to Low "
            "Risk and unlock better lending terms."
        ]
    else:
        return [
            "Focus on the highest-impact improvements first: bill payment "
            "consistency and reducing expenses relative to income will have the "
            "fastest effect on your trust score."
        ]


# ---------------------------------------------------------------------------
# Public: generate_improvement_suggestions
# ---------------------------------------------------------------------------

def generate_improvement_suggestions(score_result: dict) -> list[str]:
    """
    Generate targeted, rule-based financial improvement recommendations.

    Parameters
    ----------
    score_result : dict
        Output from ``calculate_trust_score()`` — must contain ``trust_score``
        and ``score_breakdown``.

    Returns
    -------
    list[str]
        Ordered, actionable suggestions.  Only dimensions that fall below
        their warning thresholds produce suggestions; well-performing
        dimensions are silently skipped.
    """
    breakdown   = score_result.get("score_breakdown", {})
    trust_score = score_result.get("trust_score", 0)

    suggestions: list[str] = []
    suggestions += _suggest_liquidity(breakdown.get("liquidity", 0))
    suggestions += _suggest_discipline(breakdown.get("discipline", 0))
    suggestions += _suggest_stability(breakdown.get("stability", 0))
    suggestions += _suggest_asset_protection(breakdown.get("asset_protection", 0))
    suggestions += _suggest_risk(breakdown.get("risk", 0))
    suggestions += _suggest_overall(trust_score)

    return suggestions


# ===========================================================================
# SECTION 2 — GEMINI AI FINANCIAL ADVICE
# ===========================================================================

# ---------------------------------------------------------------------------
# Prompt template
# ---------------------------------------------------------------------------

_PROMPT_TEMPLATE = textwrap.dedent("""
    You are a knowledgeable and empathetic financial advisor helping a user
    understand their Alternative Financial Trust Score.

    --- SCORE SUMMARY ---
    Trust Score : {trust_score} / 900
    Risk Tier   : {risk_tier}

    --- SCORE BREAKDOWN (each dimension scored 0–100) ---
    Liquidity        : {liquidity}
    Discipline       : {discipline}
    Stability        : {stability}
    Asset Protection : {asset_protection}
    Risk             : {risk}

    --- SYSTEM INSIGHTS ---
    {insights}

    --- IMPROVEMENT SUGGESTIONS ---
    {suggestions}

    --- YOUR TASK ---
    1. In 2–3 sentences, explain in plain language WHY the user received
       this specific trust score, referencing their strongest and weakest
       dimensions.
    2. Provide 3–5 clear, prioritised action steps the user can take in the
       next 30–90 days to meaningfully improve their score.
    3. Close with one encouraging sentence about their financial journey.

    Keep the tone professional but approachable. Translate numbers into
    real-world meaning — do not just repeat raw figures.
""").strip()

# Fallback messages — ordered by failure reason for clear diagnostics.
_FALLBACK_NO_KEY = (
    "AI advice unavailable. Configure GEMINI_API_KEY."
)
_FALLBACK_NO_SDK = (
    "AI advice unavailable. Install the Gemini SDK and dotenv: "
    "pip install google-generativeai python-dotenv"
)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _build_prompt(
    score_result: dict,
    insights: list[str],
    suggestions: list[str],
) -> str:
    """Render the Gemini prompt from score context."""
    breakdown = score_result.get("score_breakdown", {})
    return _PROMPT_TEMPLATE.format(
        trust_score      = score_result.get("trust_score", "N/A"),
        risk_tier        = score_result.get("risk_tier",   "N/A"),
        liquidity        = breakdown.get("liquidity",        "N/A"),
        discipline       = breakdown.get("discipline",       "N/A"),
        stability        = breakdown.get("stability",        "N/A"),
        asset_protection = breakdown.get("asset_protection", "N/A"),
        risk             = breakdown.get("risk",             "N/A"),
        insights    = "\n".join(f"• {i}" for i in insights)    or "None provided.",
        suggestions = "\n".join(f"• {s}" for s in suggestions) or "None provided.",
    )


def _detect_gemini_model(genai) -> str | None:
    """Return name of first Gemini model supporting generateContent, or None."""
    try:
        for model in genai.list_models():
            if "generateContent" in model.supported_generation_methods:
                return model.name
    except Exception:
        pass
    return None


def _call_gemini(prompt: str, api_key: str) -> str | None:
    """
    Call Gemini with dynamic model detection.
    Returns response text on success, None on any failure (caller falls back to Groq).
    """
    try:
        import google.generativeai as genai
    except ImportError:
        return None

    try:
        genai.configure(api_key=api_key)
        model_name = _detect_gemini_model(genai)
        if not model_name:
            return None

        model    = genai.GenerativeModel(model_name=model_name)
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception:
        return None


def _call_groq_advice(prompt: str, api_key: str) -> str | None:
    """Groq fallback for score advice generation using llama3-70b-8192."""
    try:
        from groq import Groq
    except ImportError:
        return None

    try:
        client = Groq(api_key=api_key)
        completion = client.chat.completions.create(
            model="llama3-70b-8192",
            messages=[
                {"role": "system", "content": "You are a financial advisor providing clear, structured advice."},
                {"role": "user",   "content": prompt},
            ],
            temperature=0.7,
            max_tokens=1024,
        )
        return completion.choices[0].message.content.strip()
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Public: generate_financial_advice
# ---------------------------------------------------------------------------

def generate_financial_advice(
    score_result: dict,
    insights: list[str],
    suggestions: list[str],
) -> str:
    """
    Generate an AI-powered financial advice narrative using Google Gemini.

    Reads ``GEMINI_API_KEY`` from the environment (populated from .env by
    the module-level ``load_dotenv()`` call).

    Parameters
    ----------
    score_result : dict
        Output from ``calculate_trust_score()``.
    insights : list[str]
        Output from ``generate_score_insights()``.
    suggestions : list[str]
        Output from ``generate_improvement_suggestions()``.

    Returns
    -------
    str
        Gemini-generated personalised advice narrative, or a descriptive
        fallback message if the key is missing, the SDK is not installed,
        or the API call fails.  The rest of the pipeline is never blocked.
    """
    api_key        = os.getenv("GEMINI_API_KEY", "").strip()
    groq_api_key   = os.getenv("GROQ_API_KEY",   "").strip()

    if not api_key and not groq_api_key:
        return _FALLBACK_NO_KEY

    prompt = _build_prompt(score_result, insights, suggestions)

    # Try Gemini first
    if api_key:
        result = _call_gemini(prompt, api_key)
        if result:
            return result

    # Fall back to Groq
    if groq_api_key:
        result = _call_groq_advice(prompt, groq_api_key)
        if result:
            return result

    return "AI advice temporarily unavailable. Check your API keys and try again."