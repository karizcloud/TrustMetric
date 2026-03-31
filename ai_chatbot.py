"""
ai_chatbot.py
-------------
AI-powered Financial Chatbot — Gemini primary, Groq fallback.

Provider priority:
  1. Google Gemini  — dynamically detects the first available model that
                      supports generateContent (avoids hardcoded model names
                      that go stale across SDK versions)
  2. Groq           — automatic fallback if Gemini is unavailable, returns
                      a 404 error, or no compatible model is found
  3. Static message — if neither provider is configured

Environment variables (in .env or shell):
    GEMINI_API_KEY   — Google AI Studio key
    GROQ_API_KEY     — Groq console key

Install:
    pip install google-generativeai groq python-dotenv

Public API:
    chat(question, score_context=None)  ->  str
"""

from __future__ import annotations

import os
import textwrap
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).parent / ".env", override=False)


# ---------------------------------------------------------------------------
# GROQ FALLBACK MODEL
# ---------------------------------------------------------------------------

_GROQ_MODEL = "llama3-70b-8192"

# ---------------------------------------------------------------------------
# SYSTEM PROMPT — shared by both providers
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = (
    "You are a knowledgeable, empathetic, and practical financial assistant "
    "helping users understand their financial behavior and improve their "
    "Alternative Financial Trust Score (range 300-900). "
    "Your responsibilities: answer questions about personal finance, budgeting, "
    "savings, and credit; explain what trust score dimensions mean (liquidity, "
    "discipline, stability, asset protection, risk); offer clear, actionable "
    "advice tailored to the user's situation; keep answers concise (3-6 sentences "
    "unless a detailed explanation is explicitly requested); stay focused on "
    "financial topics and politely redirect off-topic questions. "
    "If score context is provided, reference the user's specific numbers to "
    "make the advice personalised rather than generic."
)

# ---------------------------------------------------------------------------
# CONTEXT INJECTION
# ---------------------------------------------------------------------------

_CONTEXT_TEMPLATE = (
    "\n\n--- USER'S CURRENT FINANCIAL PROFILE ---\n"
    "Trust Score      : {trust_score} / 900\n"
    "Risk Tier        : {risk_tier}\n"
    "Liquidity        : {liquidity}\n"
    "Discipline       : {discipline}\n"
    "Stability        : {stability}\n"
    "Asset Protection : {asset_protection}\n"
    "Risk             : {risk}\n\n"
    "Insights:\n{insights}"
)

# ---------------------------------------------------------------------------
# FALLBACK MESSAGES
# ---------------------------------------------------------------------------

_FALLBACK_NO_PROVIDERS = (
    "AI chat unavailable. Configure at least one of: "
    "GEMINI_API_KEY or GROQ_API_KEY in your .env file."
)

_FALLBACK_BOTH_FAILED = (
    "AI chat temporarily unavailable. Both Gemini and Groq returned errors. "
    "Please check your API keys and try again."
)


# ---------------------------------------------------------------------------
# SHARED HELPERS
# ---------------------------------------------------------------------------

def _build_user_message(question: str, score_context: dict | None) -> str:
    """Combine the user question with optional score context into one string."""
    if not score_context:
        return question.strip()

    breakdown = score_context.get("score_breakdown", {})
    insights  = score_context.get("insights", [])

    context_block = _CONTEXT_TEMPLATE.format(
        trust_score      = score_context.get("trust_score", "N/A"),
        risk_tier        = score_context.get("risk_tier",   "N/A"),
        liquidity        = breakdown.get("liquidity",        "N/A"),
        discipline       = breakdown.get("discipline",       "N/A"),
        stability        = breakdown.get("stability",        "N/A"),
        asset_protection = breakdown.get("asset_protection", "N/A"),
        risk             = breakdown.get("risk",             "N/A"),
        insights         = "\n".join(f"- {i}" for i in insights) or "None provided.",
    )

    return question.strip() + context_block


# ---------------------------------------------------------------------------
# GEMINI PROVIDER — dynamic model detection
# ---------------------------------------------------------------------------

def _detect_gemini_model(genai) -> str | None:
    """
    Return the name of the first Gemini model that supports generateContent,
    or None if none is found or listing fails.
    """
    try:
        for model in genai.list_models():
            if "generateContent" in model.supported_generation_methods:
                return model.name   # e.g. "models/gemini-1.5-flash"
    except Exception:
        pass
    return None


def _call_gemini(user_message: str, api_key: str) -> str | None:
    """
    Attempt a Gemini generateContent call with dynamic model detection.
    Returns response text on success, None on any failure.
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

        model    = genai.GenerativeModel(
            model_name=model_name,
            system_instruction=_SYSTEM_PROMPT,
        )
        response = model.generate_content(user_message)
        return response.text.strip()

    except Exception:
        return None


# ---------------------------------------------------------------------------
# GROQ FALLBACK PROVIDER
# ---------------------------------------------------------------------------

def _call_groq(user_message: str, api_key: str) -> str | None:
    """
    Send the question to Groq (llama3-70b-8192).
    Returns response text on success, None on any failure.
    """
    try:
        from groq import Groq
    except ImportError:
        return None

    try:
        client = Groq(api_key=api_key)
        completion = client.chat.completions.create(
            model=_GROQ_MODEL,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user",   "content": user_message},
            ],
            temperature=0.7,
            max_tokens=1024,
        )
        return completion.choices[0].message.content.strip()

    except Exception:
        return None


# ---------------------------------------------------------------------------
# PUBLIC API
# ---------------------------------------------------------------------------

def chat(question: str, score_context: dict | None = None) -> str:
    """
    Send a financial question to the AI chatbot and return its answer.

    Provider waterfall:
        Gemini (dynamic model detection)
            -> Groq llama3-70b-8192
                -> Static fallback message

    Parameters
    ----------
    question : str
        Free-form financial question from the user.
    score_context : dict | None
        Optional trust score result enriched with an 'insights' list.

    Returns
    -------
    str
        AI-generated response, or a descriptive fallback. Never raises.
    """
    if not question or not question.strip():
        return "Please provide a question to get financial advice."

    user_message   = _build_user_message(question, score_context)
    gemini_api_key = os.getenv("GEMINI_API_KEY", "").strip()
    groq_api_key   = os.getenv("GROQ_API_KEY",   "").strip()

    # Try Gemini first
    if gemini_api_key:
        result = _call_gemini(user_message, gemini_api_key)
        if result:
            return result

    # Fall back to Groq
    if groq_api_key:
        result = _call_groq(user_message, groq_api_key)
        if result:
            return result

    # Neither provider configured
    if not gemini_api_key and not groq_api_key:
        return _FALLBACK_NO_PROVIDERS

    return _FALLBACK_BOTH_FAILED