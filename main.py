"""
main.py
-------
FastAPI backend wrapper for the Alternative Financial Trust Score Engine.

Run the server:
    uvicorn main:app --reload

Swagger UI:
    http://127.0.0.1:8000/docs
"""

from __future__ import annotations

import uuid
from pathlib import Path
from enum import Enum
from typing import Annotated

from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator

from trust_score_engine import calculate_trust_score
from bank_connector import BankConnectionError, fetch_bank_transactions, KNOWN_USERS
from score_explainer import generate_score_insights
from advisor_engine import generate_improvement_suggestions, generate_financial_advice
from data_validator import validate_financial_profile
from ai_chatbot import chat as financial_chat
from loan_engine import calculate_loan_eligibility
from score_simulator import simulate_score
from database import init_db, save_user, get_user_by_email_hash, save_score, get_scores_for_user
from security import hash_user_email, hash_password, verify_password, encrypt_score_data, decrypt_score_data


# ---------------------------------------------------------------------------
# PYDANTIC MODELS — Input Schema
# ---------------------------------------------------------------------------

class TransactionCategory(str, Enum):
    income     = "income"
    utility    = "utility"
    grocery    = "grocery"
    lifestyle  = "lifestyle"
    investment = "investment"
    rent       = "rent"


class Transaction(BaseModel):
    date:     str                 = Field(..., examples=["2024-01-05"],  description="Transaction date (YYYY-MM-DD)")
    merchant: str                 = Field(..., examples=["D-Mart"],      description="Merchant or payee name")
    amount:   float               = Field(..., gt=0,                     description="Transaction amount (must be > 0)")
    category: TransactionCategory = Field(...,                           description="Transaction category")


class BillPaymentHistory(BaseModel):
    total_bills:        int = Field(..., ge=0, description="Total number of bills due")
    bills_paid_on_time: int = Field(..., ge=0, description="Number of bills paid on time")

    @field_validator("bills_paid_on_time")
    @classmethod
    def paid_cannot_exceed_total(cls, v: int, info) -> int:
        total = info.data.get("total_bills")
        if total is not None and v > total:
            raise ValueError("bills_paid_on_time cannot exceed total_bills")
        return v


class Insurance(BaseModel):
    has_health_insurance:  bool = Field(..., description="Does the user have health insurance?")
    has_life_insurance:    bool = Field(..., description="Does the user have life insurance?")
    has_vehicle_insurance: bool = Field(..., description="Does the user have vehicle insurance?")


class TrustScoreRequest(BaseModel):
    monthly_income:       float               = Field(..., gt=0,       description="Gross monthly income")
    transactions:         list[Transaction]   = Field(..., min_length=1, description="List of financial transactions")
    bill_payment_history: BillPaymentHistory  = Field(...,             description="Bill payment track record")
    emergency_savings:    float               = Field(..., ge=0,       description="Total emergency savings balance")
    insurance:            Insurance           = Field(...,             description="Insurance coverage details")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "monthly_income": 85000,
                    "transactions": [
                        {"date": "2024-01-02", "merchant": "Salary",         "amount": 85000, "category": "income"},
                        {"date": "2024-01-05", "merchant": "City Electric",  "amount": 2200,  "category": "utility"},
                        {"date": "2024-01-07", "merchant": "D-Mart",         "amount": 5800,  "category": "grocery"},
                        {"date": "2024-01-10", "merchant": "Zomato",         "amount": 3200,  "category": "lifestyle"},
                        {"date": "2024-01-12", "merchant": "Zerodha SIP",    "amount": 10000, "category": "investment"},
                        {"date": "2024-01-15", "merchant": "House Rent",     "amount": 18000, "category": "rent"},
                        {"date": "2024-01-17", "merchant": "Netflix",        "amount": 649,   "category": "lifestyle"},
                        {"date": "2024-01-20", "merchant": "Reliance Fresh", "amount": 3100,  "category": "grocery"},
                        {"date": "2024-01-22", "merchant": "LIC Premium",    "amount": 4500,  "category": "investment"},
                        {"date": "2024-01-25", "merchant": "Amazon",         "amount": 2800,  "category": "lifestyle"},
                        {"date": "2024-01-28", "merchant": "Airtel Bill",    "amount": 999,   "category": "utility"},
                        {"date": "2024-01-30", "merchant": "Gold SGB",       "amount": 5000,  "category": "investment"},
                    ],
                    "bill_payment_history": {"total_bills": 24, "bills_paid_on_time": 22},
                    "emergency_savings": 150000,
                    "insurance": {
                        "has_health_insurance": True,
                        "has_life_insurance": True,
                        "has_vehicle_insurance": False,
                    },
                }
            ]
        }
    }


# ---------------------------------------------------------------------------
# PYDANTIC MODELS — Response Schema
# ---------------------------------------------------------------------------

class RiskTier(str, Enum):
    excellent       = "Excellent"
    low_risk        = "Low Risk"
    moderate_risk   = "Moderate Risk"
    high_risk       = "High Risk"
    very_high_risk  = "Very High Risk"


class ScoreBreakdown(BaseModel):
    liquidity:        float = Field(..., description="Income vs. expense ratio score (0–100)")
    discipline:       float = Field(..., description="Bill payment reliability score (0–100)")
    stability:        float = Field(..., description="Expense volatility score (0–100)")
    asset_protection: float = Field(..., description="Investment + emergency fund + insurance score (0–100)")
    risk:             float = Field(..., description="Lifestyle spending risk score (0–100)")


class LoanEligibility(BaseModel):
    recommended_loan:      int        = Field(..., description="Suggested micro-loan amount in INR")
    loan_range:            list[int]  = Field(..., description="[min, max] loan band for this score tier (INR)")
    repayment_reliability: float      = Field(..., description="Estimated repayment reliability % (50–95)")


class TrustScoreResponse(BaseModel):
    score_id:                 str             = Field(...,          description="Unique ID for this score calculation (UUID)")
    trust_score:              int             = Field(...,          description="Final trust score (300–900)")
    risk_tier:                RiskTier        = Field(...,          description="Borrower risk classification")
    confidence_level:         str             = Field(...,          description="Score confidence: High | Medium | Low")
    score_breakdown:          ScoreBreakdown  = Field(...,          description="Per-dimension score breakdown")
    insights:                 list[str]       = Field(default=[],   description="Human-readable financial insights")
    improvement_suggestions:  list[str]       = Field(default=[],   description="Actionable improvement recommendations")
    financial_advice:         str             = Field(default="",   description="AI-generated personalised financial advice")
    warnings:                 list[str]       = Field(default=[],   description="Data quality and validation warnings")
    loan_eligibility:         LoanEligibility = Field(...,          description="Micro-loan eligibility details")


# ---------------------------------------------------------------------------
# PYDANTIC MODELS — Chat Schema
# ---------------------------------------------------------------------------

class ScoreContextInput(BaseModel):
    """Optional trust score context to ground chatbot responses."""
    trust_score:     int            = Field(..., description="User's trust score (300–900)")
    risk_tier:       str            = Field(..., description="Risk tier label")
    score_breakdown: ScoreBreakdown = Field(..., description="Per-dimension scores")
    insights:        list[str]      = Field(default=[], description="Current score insights")


class ChatRequest(BaseModel):
    question:      str                       = Field(..., min_length=1, description="Financial question to ask the AI advisor")
    score_context: ScoreContextInput | None  = Field(default=None,      description="Optional trust score context for personalised answers")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "question": "How can I improve my financial stability score?",
                    "score_context": None
                },
                {
                    "question": "Why is my score considered Moderate Risk and what should I prioritise first?",
                    "score_context": {
                        "trust_score": 657,
                        "risk_tier": "Moderate Risk",
                        "score_breakdown": {
                            "liquidity": 50.0,
                            "discipline": 79.17,
                            "stability": 33.76,
                            "asset_protection": 57.5,
                            "risk": 78.96
                        },
                        "insights": [
                            "Income moderately covers expenses with limited surplus.",
                            "Good bill payment reliability with occasional missed payments.",
                            "High spending volatility reduces financial stability and predictability."
                        ]
                    }
                }
            ]
        }
    }


class ChatResponse(BaseModel):
    response: str = Field(..., description="AI-generated financial advice response")


# ---------------------------------------------------------------------------
# PYDANTIC MODELS — Simulation Schema
# ---------------------------------------------------------------------------

class SimulationChanges(BaseModel):
    reduce_lifestyle_spending_percent: float = Field(
        default=0.0, ge=0, le=100,
        description="Reduce each lifestyle transaction amount by this percentage (0–100)",
    )
    increase_investment_percent: float = Field(
        default=0.0, ge=0, le=100,
        description="Increase each investment transaction amount by this percentage (0–100)",
    )


class SimulateScoreRequest(BaseModel):
    current_data:        TrustScoreRequest = Field(..., description="User's current financial dataset")
    simulation_changes:  SimulationChanges = Field(..., description="Hypothetical behaviour changes to simulate")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "current_data": {
                        "monthly_income": 55000,
                        "transactions": [
                            {"date": "2024-01-01", "merchant": "Salary",       "amount": 55000, "category": "income"},
                            {"date": "2024-01-03", "merchant": "House Rent",   "amount": 14000, "category": "rent"},
                            {"date": "2024-01-05", "merchant": "MSEB",         "amount": 1400,  "category": "utility"},
                            {"date": "2024-01-07", "merchant": "D-Mart",       "amount": 4500,  "category": "grocery"},
                            {"date": "2024-01-09", "merchant": "Zerodha SIP",  "amount": 3000,  "category": "investment"},
                            {"date": "2024-01-11", "merchant": "Zomato",       "amount": 2200,  "category": "lifestyle"},
                            {"date": "2024-01-13", "merchant": "Jio",          "amount": 699,   "category": "utility"},
                            {"date": "2024-01-15", "merchant": "Reliance",     "amount": 2900,  "category": "grocery"},
                            {"date": "2024-01-17", "merchant": "BookMyShow",   "amount": 800,   "category": "lifestyle"},
                            {"date": "2024-01-19", "merchant": "Amazon",       "amount": 3500,  "category": "lifestyle"},
                            {"date": "2024-01-21", "merchant": "LIC Premium",  "amount": 2500,  "category": "investment"},
                            {"date": "2024-01-25", "merchant": "Uber",         "amount": 1500,  "category": "lifestyle"},
                        ],
                        "bill_payment_history": {"total_bills": 24, "bills_paid_on_time": 19},
                        "emergency_savings": 45000,
                        "insurance": {
                            "has_health_insurance": True,
                            "has_life_insurance": False,
                            "has_vehicle_insurance": False,
                        },
                    },
                    "simulation_changes": {
                        "reduce_lifestyle_spending_percent": 30,
                        "increase_investment_percent": 20,
                    },
                }
            ]
        }
    }


class SimulateScoreResponse(BaseModel):
    current_score:      int = Field(..., description="Trust score using the original dataset")
    simulated_score:    int = Field(..., description="Trust score after applying simulation changes")
    score_improvement:  int = Field(..., description="Difference: simulated_score − current_score (positive = improvement)")
    new_risk_tier:      str = Field(..., description="Risk tier for the simulated score")
    simulation_insight: str = Field(..., description="Plain-English explanation of which dimensions changed and why")


# ---------------------------------------------------------------------------
# PYDANTIC MODELS — Auth Schema
# ---------------------------------------------------------------------------

class RegisterRequest(BaseModel):
    email:    str = Field(..., description="User email address (stored as SHA-256 hash — never in plaintext)")
    password: str = Field(..., min_length=8, description="Password (min 8 characters, stored as PBKDF2 hash)")


class RegisterResponse(BaseModel):
    message: str = Field(..., description="Registration status message")
    user_id: int = Field(..., description="Assigned user ID")


class LoginRequest(BaseModel):
    email:    str = Field(..., description="Email address used during registration")
    password: str = Field(..., description="Plaintext password to verify")


class LoginResponse(BaseModel):
    message:    str = Field(..., description="Login status message")
    user_id:    int = Field(..., description="Authenticated user ID — pass as X-User-ID header")
    email_hash: str = Field(..., description="Your hashed email identifier")


class StoredScoreEntry(BaseModel):
    score_id:   str  = Field(..., description="Unique score ID (UUID)")
    created_at: str  = Field(..., description="When this score was calculated")
    score_data: dict = Field(..., description="Decrypted score result")


class MyScoresResponse(BaseModel):
    user_id: int                    = Field(..., description="Your user ID")
    count:   int                    = Field(..., description="Total stored scores")
    scores:  list[StoredScoreEntry] = Field(..., description="Your decrypted score history")


# ---------------------------------------------------------------------------
# APP & ROUTES
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Alternative Financial Trust Score API",
    description=(
        "Rule-based scoring engine that calculates a transparent financial trust score "
        "(300–900) for individuals without traditional credit histories.\n\n"
        "**Score Endpoints:**\n"
        "- `POST /calculate-trust-score` — score from request body\n"
        "- `POST /calculate-trust-score/{user_id}` — score from simulated bank connector\n"
        "- `POST /simulate-score` — what-if score simulator\n"
        "- `POST /financial-chat` — AI financial advisor chatbot\n\n"
        "**User & Storage Endpoints:**\n"
        "- `POST /register` — create account (email stored as SHA-256 hash)\n"
        "- `POST /login` — verify credentials, receive user_id\n"
        "- `GET /my-scores` — retrieve your encrypted score history\n\n"
        "Pass `X-User-ID` header to link score calculations to your account."
    ),
    version="2.0.0",
)

# ---------------------------------------------------------------------------
# CORS  — allows the HTML frontend (opened from file:// or any local server)
# to call the API without being blocked by the browser's same-origin policy.
# ---------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],          # In production: replace with your actual domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialise SQLite database and create tables on startup
init_db()

# ---------------------------------------------------------------------------
# STATIC FILES — serve the HTML frontend from the same folder as main.py
# Now opening http://127.0.0.1:8000 loads landing.html automatically
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent

app.mount("/static", StaticFiles(directory=BASE_DIR), name="static")


@app.get("/", include_in_schema=False)
def root():
    """Serve landing.html as the app entry point."""
    html_file = BASE_DIR / "landing.html"
    return HTMLResponse(content=html_file.read_text(encoding="utf-8"))


@app.get("/landing.html", include_in_schema=False)
def serve_landing():
    return HTMLResponse(content=(BASE_DIR / "landing.html").read_text(encoding="utf-8"))


@app.get("/luxury-login.html", include_in_schema=False)
def serve_login():
    return HTMLResponse(content=(BASE_DIR / "luxury-login.html").read_text(encoding="utf-8"))


@app.get("/dashboard.html", include_in_schema=False)
def serve_dashboard():
    return HTMLResponse(content=(BASE_DIR / "dashboard.html").read_text(encoding="utf-8"))


@app.get(
    "/users",
    summary="List available bank users",
    response_description="User IDs that can be used with the bank connector endpoint",
)
def list_users() -> JSONResponse:
    """Returns all user IDs available in the simulated bank data store."""
    return JSONResponse({"available_users": KNOWN_USERS})


@app.post(
    "/calculate-trust-score",
    response_model=TrustScoreResponse,
    summary="Calculate trust score from request body",
    response_description="Trust score with risk tier and detailed score breakdown",
)
def calculate_trust_score_endpoint(
    payload:    TrustScoreRequest,
    x_user_id:  int | None = Header(default=None, description="Optional: your user ID to save this score to your account"),
) -> TrustScoreResponse:
    """
    Accepts a full user financial dataset in the request body and returns a
    trust score between **300–900** with a risk tier and per-dimension breakdown.

    Optionally pass **`X-User-ID`** header (from `/login`) to save this score
    to your account and retrieve it later via `GET /my-scores`.

    **Score Tiers:**
    | Range    | Tier           |
    |----------|----------------|
    | 820–900  | Excellent      |
    | 740–819  | Low Risk       |
    | 650–739  | Moderate Risk  |
    | 550–649  | High Risk      |
    | 300–549  | Very High Risk |
    """
    try:
        data        = payload.model_dump()
        result      = calculate_trust_score(data)
        insights    = generate_score_insights(result)
        suggestions = generate_improvement_suggestions(result)
        advice      = generate_financial_advice(result, insights, suggestions)
        validation  = validate_financial_profile(data, result)

        # Compute total expenses for the improved loan formula
        total_expenses = sum(
            t["amount"] for t in data["transactions"]
            if t["category"] != "income"
        )
        loan = calculate_loan_eligibility(
            trust_score      = result["trust_score"],
            monthly_income   = data["monthly_income"],
            total_expenses   = total_expenses,
            stability_score  = result["score_breakdown"]["stability"],
            discipline_score = result["score_breakdown"]["discipline"],
        )

        # Generate a unique ID for this score calculation
        score_id = str(uuid.uuid4())

        result["score_id"]               = score_id
        result["insights"]               = insights
        result["improvement_suggestions"] = suggestions
        result["financial_advice"]       = advice
        result["confidence_level"]       = validation["confidence_level"]
        result["warnings"]               = validation["warnings"]
        result["loan_eligibility"]       = loan

        # Persist to database if a logged-in user ID was provided
        if x_user_id is not None:
            score_payload = {
                "trust_score":            result["trust_score"],
                "risk_tier":              result["risk_tier"],
                "score_breakdown":        result["score_breakdown"],
                "loan_eligibility":       loan,
                "insights":               insights,
                "improvement_suggestions": suggestions,
            }
            encrypted = encrypt_score_data(score_payload)
            save_score(score_id, x_user_id, encrypted, data["transactions"])

        return TrustScoreResponse(**result)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Scoring engine error: {str(exc)}")


@app.post(
    "/calculate-trust-score/{user_id}",
    response_model=TrustScoreResponse,
    summary="Calculate trust score via bank connector",
    response_description="Trust score fetched and scored from simulated bank data",
)
def calculate_trust_score_by_user(
    user_id:    str,
    x_user_id:  int | None = Header(default=None, description="Optional: your user ID to save this score"),
) -> TrustScoreResponse:
    """
    Fetches the financial dataset for **user_id** from the simulated bank
    connector and returns the calculated trust score.

    **Available user IDs:** `good_user` · `average_user` · `risky_user`
    """
    try:
        data = fetch_bank_transactions(user_id)
    except BankConnectionError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    try:
        result      = calculate_trust_score(data)
        insights    = generate_score_insights(result)
        suggestions = generate_improvement_suggestions(result)
        advice      = generate_financial_advice(result, insights, suggestions)
        validation  = validate_financial_profile(data, result)

        total_expenses = sum(
            t["amount"] for t in data["transactions"]
            if t["category"] != "income"
        )
        loan = calculate_loan_eligibility(
            trust_score      = result["trust_score"],
            monthly_income   = data["monthly_income"],
            total_expenses   = total_expenses,
            stability_score  = result["score_breakdown"]["stability"],
            discipline_score = result["score_breakdown"]["discipline"],
        )

        score_id = str(uuid.uuid4())

        result["score_id"]               = score_id
        result["insights"]               = insights
        result["improvement_suggestions"] = suggestions
        result["financial_advice"]       = advice
        result["confidence_level"]       = validation["confidence_level"]
        result["warnings"]               = validation["warnings"]
        result["loan_eligibility"]       = loan

        if x_user_id is not None:
            score_payload = {
                "trust_score":            result["trust_score"],
                "risk_tier":              result["risk_tier"],
                "score_breakdown":        result["score_breakdown"],
                "loan_eligibility":       loan,
                "insights":               insights,
                "improvement_suggestions": suggestions,
            }
            encrypted = encrypt_score_data(score_payload)
            save_score(score_id, x_user_id, encrypted, data["transactions"])

        return TrustScoreResponse(**result)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Scoring engine error: {str(exc)}")


@app.post(
    "/financial-chat",
    response_model=ChatResponse,
    summary="AI Financial Advisor Chatbot",
    response_description="Gemini-powered response to a financial question",
)
def financial_chat_endpoint(payload: ChatRequest) -> ChatResponse:
    """
    Ask the AI financial advisor any question about personal finance,
    budgeting, savings, or trust score improvement.

    Optionally include your **trust score context** (score, tier, breakdown,
    insights) to receive personalised advice referencing your exact numbers
    instead of generic guidance.

    **Without context** — general financial Q&A:
    ```json
    { "question": "What is a good emergency fund size?" }
    ```

    **With context** — score-aware personalised advice:
    ```json
    {
      "question": "Why is my score low and what should I fix first?",
      "score_context": {
        "trust_score": 518,
        "risk_tier": "Very High Risk",
        "score_breakdown": { "liquidity": 20, "discipline": 45, "stability": 54, "asset_protection": 18, "risk": 41 },
        "insights": ["Expenses are close to or exceeding income."]
      }
    }
    ```

    Requires `GEMINI_API_KEY` in your `.env` file or environment.
    """
    try:
        score_context = payload.score_context.model_dump() if payload.score_context else None
        reply = financial_chat(payload.question, score_context)
        return ChatResponse(response=reply)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Chat error: {str(exc)}")


@app.post(
    "/simulate-score",
    response_model=SimulateScoreResponse,
    summary="Simulate trust score impact of financial behaviour changes",
    response_description="Current vs simulated score comparison",
)
def simulate_score_endpoint(payload: SimulateScoreRequest) -> SimulateScoreResponse:
    """
    Test how targeted financial improvements would affect the trust score —
    without modifying any real data.

    **Simulation levers:**

    | Parameter | Effect |
    |---|---|
    | `reduce_lifestyle_spending_percent` | Scales down every lifestyle transaction by X% |
    | `increase_investment_percent` | Scales up every investment transaction by X% |

    **Example:** reduce lifestyle by 30% + grow investments by 20%
    ```json
    {
      "simulation_changes": {
        "reduce_lifestyle_spending_percent": 30,
        "increase_investment_percent": 20
      }
    }
    ```

    The original dataset is never mutated — simulation runs on a deep copy.
    """
    try:
        # Convert Pydantic model → plain dict the simulator already understands
        data    = payload.current_data.model_dump()
        changes = payload.simulation_changes.model_dump()
        result  = simulate_score(data, changes)
        return SimulateScoreResponse(**result)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Simulation error: {str(exc)}")


# ---------------------------------------------------------------------------
# AUTH ENDPOINTS
# ---------------------------------------------------------------------------

@app.post(
    "/register",
    response_model=RegisterResponse,
    summary="Register a new user account",
    status_code=201,
)
def register(payload: RegisterRequest) -> RegisterResponse:
    """
    Create a new user account.

    - Email is **hashed with SHA-256** before storage — the real email is never saved.
    - Password is **hashed with PBKDF2-HMAC-SHA256** (260,000 iterations, random salt).
    - No plaintext credentials are ever written to disk.
    """
    email_hash    = hash_user_email(payload.email)
    password_hash = hash_password(payload.password)
    try:
        user_id = save_user(email_hash, password_hash)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    return RegisterResponse(message="Account created successfully.", user_id=user_id)


@app.post(
    "/login",
    response_model=LoginResponse,
    summary="Log in and retrieve your user ID",
)
def login(payload: LoginRequest) -> LoginResponse:
    """
    Verify credentials and return your **user_id**.

    Use the returned `user_id` as the **`X-User-ID`** header when calling
    `POST /calculate-trust-score` to save scores to your account.
    """
    email_hash = hash_user_email(payload.email)
    user       = get_user_by_email_hash(email_hash)

    if user is None or not verify_password(payload.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password.")

    return LoginResponse(
        message    = "Login successful.",
        user_id    = user["id"],
        email_hash = email_hash,
    )


# ---------------------------------------------------------------------------
# SCORE RETRIEVAL ENDPOINT
# ---------------------------------------------------------------------------

@app.get(
    "/my-scores",
    response_model=MyScoresResponse,
    summary="Retrieve your saved score history",
)
def my_scores(
    x_user_id: int = Header(..., description="Your user ID from POST /login"),
) -> MyScoresResponse:
    """
    Retrieve all trust scores saved to your account.

    Requires the **`X-User-ID`** header (your numeric user ID returned by `/login`).

    Each score entry was encrypted with Fernet before storage and is
    decrypted here on the fly — the database contains no readable financial data.
    """
    rows = get_scores_for_user(x_user_id)

    decrypted_scores: list[StoredScoreEntry] = []
    for row in rows:
        try:
            score_data = decrypt_score_data(row["encrypted_score_data"])
        except ValueError:
            score_data = {"error": "Could not decrypt — encryption key may have changed."}

        decrypted_scores.append(StoredScoreEntry(
            score_id   = row["score_id"],
            created_at = str(row["created_at"]),
            score_data = score_data,
        ))

    return MyScoresResponse(
        user_id = x_user_id,
        count   = len(decrypted_scores),
        scores  = decrypted_scores,
    )


# ---------------------------------------------------------------------------
# PDF REPORT ENDPOINT
# ---------------------------------------------------------------------------

import io
from datetime import datetime
from fastapi.responses import StreamingResponse
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
from pydantic import BaseModel as _BaseModel


class _SBpdf(_BaseModel):
    liquidity:        float = 0
    discipline:       float = 0
    stability:        float = 0
    asset_protection: float = 0
    risk:             float = 0


class _LEpdf(_BaseModel):
    recommended_loan:      int       = 0
    loan_range:            list[int] = [0, 0]
    repayment_reliability: float     = 0


class PDFReportRequest(_BaseModel):
    trust_score:             int
    risk_tier:               str
    confidence_level:        str      = "Medium"
    score_breakdown:         _SBpdf   = _SBpdf()
    insights:                list[str] = []
    improvement_suggestions: list[str] = []
    loan_eligibility:        _LEpdf | None = None


def _hx(c): return c.hexval().lstrip("#")


def _build_pdf(d: PDFReportRequest) -> bytes:
    buf   = io.BytesIO()
    W, _  = A4
    mg    = 18 * mm

    GOLD  = colors.HexColor("#D4AF37")
    GDIM  = colors.HexColor("#2A200A")
    D2    = colors.HexColor("#1A1A1A")
    D3    = colors.HexColor("#242424")
    WHITE = colors.white
    GRAY  = colors.HexColor("#9CA3AF")
    GREEN = colors.HexColor("#22c55e")
    AMBER = colors.HexColor("#eab308")
    RED   = colors.HexColor("#ef4444")

    # FIX: insight/suggestion text was white on white (no background).
    # Use a visible dark color that works on the plain page background.
    BODY_TEXT = colors.HexColor("#1A1A1A")

    def tier_col(t):
        t = t.lower()
        if "excellent" in t or "low" in t: return GREEN
        if "moderate" in t:                return AMBER
        return RED

    def dim_col(v):
        if v >= 70: return GREEN
        if v >= 45: return AMBER
        return RED

    def ps(name, **kw): return ParagraphStyle(name, **kw)

    doc = SimpleDocTemplate(buf, pagesize=A4,
                            leftMargin=mg, rightMargin=mg,
                            topMargin=12*mm, bottomMargin=12*mm)
    s = []

    # ── Title ─────────────────────────────────────────────────────────────────
    s.append(Paragraph("TrustMetric Financial Report",
        ps("title", fontName="Helvetica-Bold", fontSize=22,
           textColor=GOLD, alignment=1, spaceAfter=2)))
    s.append(Paragraph(datetime.now().strftime("Generated %d %b %Y at %H:%M"),
        ps("sub", fontName="Helvetica", fontSize=9,
           textColor=GRAY, alignment=1, spaceAfter=10)))
    s.append(HRFlowable(width="100%", thickness=1, color=GOLD))
    s.append(Spacer(1, 10))

    # ── Score highlight block ──────────────────────────────────────────────────
    sc = tier_col(d.risk_tier)
    hero = Table([[
        [Paragraph("TRUST SCORE", ps("sl", fontName="Helvetica", fontSize=10, textColor=GRAY)),
         Paragraph(f"<font color='#{_hx(sc)}'><b>{d.trust_score}</b></font>",
             ps("sv", fontName="Helvetica-Bold", fontSize=54, textColor=WHITE, leading=58)),
         Paragraph("/ 900", ps("sof", fontName="Helvetica", fontSize=10, textColor=GRAY))],
        [Paragraph("RISK TIER", ps("rl", fontName="Helvetica", fontSize=10, textColor=GRAY)),
         Paragraph(f"<font color='#{_hx(sc)}'><b>{d.risk_tier}</b></font>",
             ps("rv", fontName="Helvetica-Bold", fontSize=16, textColor=WHITE, spaceAfter=6)),
         Paragraph("CONFIDENCE", ps("cl", fontName="Helvetica", fontSize=10, textColor=GRAY)),
         Paragraph(f"<b>{d.confidence_level}</b>",
             ps("cv", fontName="Helvetica-Bold", fontSize=13, textColor=WHITE))],
    ]], colWidths=[(W - 2*mg)*0.45, (W - 2*mg)*0.55])
    hero.setStyle(TableStyle([
        ("BACKGROUND",    (0,0),(-1,-1), D2),
        ("TOPPADDING",    (0,0),(-1,-1), 16),
        ("BOTTOMPADDING", (0,0),(-1,-1), 16),
        ("LEFTPADDING",   (0,0),(-1,-1), 20),
        ("RIGHTPADDING",  (0,0),(-1,-1), 20),
        ("VALIGN",        (0,0),(-1,-1), "MIDDLE"),
        ("LINEAFTER",     (0,0),(0,-1),  0.5, GDIM),
    ]))
    s.append(hero)
    s.append(Spacer(1, 14))
    s.append(HRFlowable(width="100%", thickness=0.5, color=GDIM))
    s.append(Spacer(1, 10))

    # ── Score Breakdown ────────────────────────────────────────────────────────
    s.append(Paragraph("Score Breakdown",
        ps("sec1", fontName="Helvetica-Bold", fontSize=13, textColor=GOLD, spaceAfter=6)))
    dims = [
        ("Liquidity",        d.score_breakdown.liquidity),
        ("Discipline",       d.score_breakdown.discipline),
        ("Stability",        d.score_breakdown.stability),
        ("Asset Protection", d.score_breakdown.asset_protection),
        ("Risk",             d.score_breakdown.risk),
    ]
    rows = [[
        Paragraph("<b>Dimension</b>",  ps("h0", fontName="Helvetica-Bold", fontSize=10, textColor=GOLD)),
        Paragraph("<b>Score /100</b>", ps("h1", fontName="Helvetica-Bold", fontSize=10, textColor=GOLD)),
        Paragraph("<b>Level</b>",      ps("h2", fontName="Helvetica-Bold", fontSize=10, textColor=GOLD)),
    ]]
    for label, val in dims:
        c  = dim_col(val)
        lv = "Good" if val >= 70 else ("Fair" if val >= 45 else "Low")
        rows.append([
            Paragraph(f"<b>{label}</b>",
                ps(f"d_{label}", fontName="Helvetica-Bold", fontSize=10, textColor=WHITE)),
            Paragraph(f"<font color='#{_hx(c)}'><b>{val:.1f}</b></font>",
                ps(f"v_{label}", fontName="Helvetica", fontSize=10, textColor=WHITE)),
            Paragraph(f"<font color='#{_hx(c)}'>{lv}</font>",
                ps(f"l_{label}", fontName="Helvetica", fontSize=10, textColor=WHITE)),
        ])
    bt = Table(rows, colWidths=[(W-2*mg)*0.38, (W-2*mg)*0.22, (W-2*mg)*0.40])
    bt.setStyle(TableStyle([
        ("BACKGROUND",    (0,0),(-1, 0), GDIM),
        ("ROWBACKGROUNDS",(0,1),(-1,-1), [D2, D3]),
        ("GRID",          (0,0),(-1,-1), 0.3, GDIM),
        ("TOPPADDING",    (0,0),(-1,-1), 8),
        ("BOTTOMPADDING", (0,0),(-1,-1), 8),
        ("LEFTPADDING",   (0,0),(-1,-1), 10),
        ("RIGHTPADDING",  (0,0),(-1,-1), 10),
        ("VALIGN",        (0,0),(-1,-1), "MIDDLE"),
    ]))
    s.append(bt)
    s.append(Spacer(1, 14))
    s.append(HRFlowable(width="100%", thickness=0.5, color=GDIM))
    s.append(Spacer(1, 10))

    # ── Insights ───────────────────────────────────────────────────────────────
    # FIX: was textColor=WHITE — invisible on white page. Changed to BODY_TEXT.
    if d.insights:
        s.append(Paragraph("Insights",
            ps("sec2", fontName="Helvetica-Bold", fontSize=13, textColor=GOLD, spaceAfter=4)))
        for line in d.insights:
            s.append(Paragraph(f"• {line}",
                ps(f"ins_{abs(hash(line))%99999}", fontName="Helvetica", fontSize=10,
                   textColor=BODY_TEXT, leftIndent=12, spaceAfter=4, leading=15)))
        s.append(Spacer(1, 10))
        s.append(HRFlowable(width="100%", thickness=0.5, color=GDIM))
        s.append(Spacer(1, 10))

    # ── Improvement Suggestions ────────────────────────────────────────────────
    # FIX: same white-text bug fixed here too.
    if d.improvement_suggestions:
        s.append(Paragraph("Improvement Suggestions",
            ps("sec3", fontName="Helvetica-Bold", fontSize=13, textColor=GOLD, spaceAfter=4)))
        for line in d.improvement_suggestions:
            s.append(Paragraph(f"• {line}",
                ps(f"sug_{abs(hash(line))%99999}", fontName="Helvetica", fontSize=10,
                   textColor=BODY_TEXT, leftIndent=12, spaceAfter=4, leading=15)))
        s.append(Spacer(1, 10))
        s.append(HRFlowable(width="100%", thickness=0.5, color=GDIM))
        s.append(Spacer(1, 10))

    # ── Loan Eligibility ───────────────────────────────────────────────────────
    # FIX: splitByRow=0 keeps all three rows on the same page — no more split.
    if d.loan_eligibility:
        le = d.loan_eligibility
        s.append(Paragraph("Loan Eligibility",
            ps("sec4", fontName="Helvetica-Bold", fontSize=13, textColor=GOLD, spaceAfter=4)))
        lt = Table([
            ["Recommended Loan",      f"Rs. {le.recommended_loan:,}"],
            ["Eligible Range",        f"Rs. {le.loan_range[0]:,}  -  Rs. {le.loan_range[1]:,}"],
            ["Repayment Reliability", f"{le.repayment_reliability:.1f}%"],
        ], colWidths=[(W-2*mg)*0.42, (W-2*mg)*0.58],
           splitByRow=0)   # FIX: never split this table across pages
        lt.setStyle(TableStyle([
            ("ROWBACKGROUNDS",(0,0),(-1,-1), [D2, D3]),
            ("TEXTCOLOR",     (0,0),(0,-1),  GRAY),
            ("TEXTCOLOR",     (1,0),(1,-1),  GOLD),
            ("FONTNAME",      (0,0),(-1,-1), "Helvetica"),
            ("FONTNAME",      (1,0),(1,-1),  "Helvetica-Bold"),
            ("FONTSIZE",      (0,0),(-1,-1), 10),
            ("GRID",          (0,0),(-1,-1), 0.3, GDIM),
            ("TOPPADDING",    (0,0),(-1,-1), 9),
            ("BOTTOMPADDING", (0,0),(-1,-1), 9),
            ("LEFTPADDING",   (0,0),(-1,-1), 12),
            ("RIGHTPADDING",  (0,0),(-1,-1), 12),
        ]))
        s.append(lt)
        s.append(Spacer(1, 14))
        s.append(HRFlowable(width="100%", thickness=0.5, color=GDIM))
        s.append(Spacer(1, 10))

    # ── Footer ─────────────────────────────────────────────────────────────────
    s.append(HRFlowable(width="100%", thickness=1, color=GOLD))
    s.append(Spacer(1, 4))
    s.append(Paragraph("Generated by TrustMetric AI",
        ps("ft", fontName="Helvetica", fontSize=9, textColor=GRAY, alignment=1)))

    doc.build(s)
    buf.seek(0)
    return buf.read()


@app.post(
    "/generate-pdf-report",
    summary="Generate a downloadable PDF trust score report",
    response_description="PDF file download",
)
def generate_pdf_report(payload: PDFReportRequest):
    """
    Accepts the same response object returned by /calculate-trust-score
    and returns a styled, downloadable PDF report.
    """
    try:
        pdf_bytes = _build_pdf(payload)
        return StreamingResponse(
            io.BytesIO(pdf_bytes),
            media_type="application/pdf",
            headers={"Content-Disposition": 'attachment; filename="trustmetric_report.pdf"'},
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"PDF generation error: {str(exc)}")