# TrustMetric — Alternative Financial Trust Score System

> A full-stack AI-powered financial trust scoring platform built for individuals without traditional credit histories. Built for hackathon.

---

## What It Does

TrustMetric calculates a **financial trust score (300–900)** based on real transaction behaviour — not just credit history. It analyses how people actually spend, save, and pay bills to produce a transparent, explainable financial identity score.

**Key capabilities:**
- Trust score calculation from transaction data
- Micro-loan eligibility recommendation
- What-if score simulator
- AI financial advisor chatbot (Gemini + Groq)
- Secure encrypted score history
- File upload support — JSON, CSV, PDF bank statements

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.12, FastAPI, Uvicorn |
| Frontend | Vanilla HTML/CSS/JS, Chart.js, WebGL |
| Database | SQLite (via Python `sqlite3`) |
| Security | SHA-256 (email), PBKDF2-HMAC-SHA256 (password), Fernet AES-128 (score data) |
| AI | Google Gemini (primary), Groq llama3-70b (fallback) |
| PDF Parsing | PDF.js (loaded on demand) |
| CSV Parsing | PapaParse |

---

## Project Structure

```
TrustMetric/
│
├── main.py                    # FastAPI app — all endpoints, serves HTML
│
├── trust_score_engine.py      # Core scoring logic (300–900)
├── transaction_cleaner.py     # Normalises raw transaction descriptions
├── score_explainer.py         # Generates human-readable score insights
├── advisor_engine.py          # Rule-based suggestions + Gemini/Groq advice
├── ai_chatbot.py              # AI chatbot (Gemini → Groq fallback)
├── loan_engine.py             # Micro-loan eligibility calculator
├── score_simulator.py         # What-if score simulator
├── data_validator.py          # Data quality checks + confidence level
├── bank_connector.py          # Simulated bank data loader
│
├── database.py                # SQLite DB layer (users, scores, transactions)
├── security.py                # Email hash, password hash, Fernet encryption
│
├── landing.html               # Landing page
├── luxury-login.html          # Login / Register page
├── dashboard.html             # Main dashboard (all features)
│
├── .env.example               # Environment variable template
├── trust_score.db             # SQLite database (auto-created on first run)
│
└── bank_data/
    ├── good_user.json         # Demo: score ~741, Low Risk
    ├── average_user.json      # Demo: score ~657, Moderate Risk
    └── risky_user.json        # Demo: score ~518, Very High Risk
```

---

## Quick Start

### 1. Install dependencies

```bash
pip install fastapi uvicorn python-dotenv cryptography
```

### 2. Set up environment variables

```bash
# Copy the example file
cp .env.example .env
```

Edit `.env`:

```env
# Generate this key by running:
# python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
SCORE_ENCRYPTION_KEY=your_generated_key_here

# At least one AI key required for chatbot and financial advice
GEMINI_API_KEY=your_gemini_key      # https://aistudio.google.com/app/apikey
GROQ_API_KEY=your_groq_key          # https://console.groq.com/keys (free tier)
```

> **Note:** The app starts and all core features work even without a `.env` file. Only the AI chatbot and financial advice text require an API key.

### 3. Run the server

```bash
uvicorn main:app --reload
```

### 4. Open in browser

```
http://127.0.0.1:8000
```

That's it. FastAPI serves both the HTML frontend and the API from the same server.

---

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/` | Landing page |
| `GET` | `/luxury-login.html` | Login / Register page |
| `GET` | `/dashboard.html` | Main dashboard |
| `POST` | `/register` | Create user account |
| `POST` | `/login` | Login, returns `user_id` |
| `POST` | `/calculate-trust-score` | Calculate score from uploaded data |
| `POST` | `/calculate-trust-score/{user_id}` | Calculate score from demo bank data |
| `POST` | `/simulate-score` | Simulate score changes |
| `POST` | `/financial-chat` | AI financial advisor chatbot |
| `GET` | `/my-scores` | Retrieve saved score history |

Interactive API docs available at:  
`http://127.0.0.1:8000/docs`

---

## Authentication

Register and login to save your scores across sessions.

```bash
# Register
POST /register
{ "email": "you@example.com", "password": "yourpassword" }

# Login — returns user_id
POST /login
{ "email": "you@example.com", "password": "yourpassword" }
# Response: { "user_id": 1, "message": "Login successful." }
```

Include `X-User-ID` header on score requests to save results:

```
X-User-ID: 1
```

**Security:**
- Email stored as **SHA-256 hash** — plaintext never saved
- Password hashed with **PBKDF2-HMAC-SHA256** (260,000 iterations, random salt)
- Score data **Fernet-encrypted** (AES-128-CBC + HMAC) before storing in database

---

## Trust Score Input Format

```json
{
  "monthly_income": 75000,
  "bill_payment_history": {
    "total_bills": 24,
    "bills_paid_on_time": 20
  },
  "emergency_savings": 150000,
  "insurance": {
    "has_health_insurance": true,
    "has_life_insurance": false,
    "has_vehicle_insurance": false
  },
  "transactions": [
    { "date": "2024-01-01", "merchant": "Employer Salary", "amount": 75000, "category": "income" },
    { "date": "2024-01-03", "merchant": "House Rent",      "amount": 18000, "category": "rent" },
    { "date": "2024-01-07", "merchant": "D-Mart",          "amount": 4200,  "category": "grocery" },
    { "date": "2024-01-09", "merchant": "Zerodha SIP",     "amount": 8000,  "category": "investment" },
    { "date": "2024-01-11", "merchant": "Zomato",          "amount": 1800,  "category": "lifestyle" }
  ]
}
```

**Valid transaction categories:** `income` · `rent` · `utility` · `grocery` · `investment` · `lifestyle`

---

## How the Score Works

The trust score is calculated across **5 dimensions**, each scored 0–100:

| Dimension | What it measures | Weight |
|---|---|---|
| **Liquidity** | Income vs total expenses ratio | 25% |
| **Discipline** | Bills paid on time percentage | 25% |
| **Stability** | Spending consistency (low volatility = higher score) | 20% |
| **Asset Protection** | Investments + emergency savings + insurance | 15% |
| **Risk** | Lifestyle/discretionary spending ratio | 15% |

**Final score formula:**
```
raw_score = (0.25 × liquidity) + (0.25 × discipline) + (0.20 × stability)
          + (0.15 × asset_protection) + (0.15 × risk)

trust_score = 300 + (raw_score / 100) × 600     → range: 300–900
```

**Score tiers:**

| Range | Tier |
|---|---|
| 820–900 | Excellent |
| 740–819 | Low Risk |
| 650–739 | Moderate Risk |
| 550–649 | High Risk |
| 300–549 | Very High Risk |

---

## Loan Eligibility

Loan recommendations are calculated from actual cash flow:

```
surplus            = monthly_income − total_expenses
repayment_capacity = surplus × 0.4
risk_factor        = trust_score / 900
recommended_loan   = repayment_capacity × risk_factor × 12
```

Clamped between **₹5,000 minimum** and **₹50,000 maximum**.

Repayment reliability is a weighted score of:
- Trust score (50%) + Discipline (30%) + Stability (20%) — clamped 50%–95%

---

## Score Simulator

Test "what if" scenarios without changing real data:

```json
POST /simulate-score
{
  "current_data": { ...same as calculate-trust-score... },
  "simulation_changes": {
    "reduce_lifestyle_spending_percent": 20,
    "increase_investment_percent": 15
  }
}
```

Response includes:
- `current_score` — your baseline score
- `simulated_score` — score after changes
- `score_improvement` — the delta (+/-)
- `new_risk_tier` — tier after simulation
- `simulation_insight` — plain-English explanation of what changed and why

---

## File Upload Support

The dashboard accepts three file formats:

| Format | How it's processed |
|---|---|
| **JSON** | Parsed directly. If it contains a full dataset object, form fields auto-fill. If it's a transactions array, it's used as-is. |
| **CSV** | Parsed with PapaParse. Columns: `date`, `merchant`, `amount`, `category`. Category is inferred from merchant name if not provided. |
| **PDF** | Text extracted with PDF.js. Transaction rows are parsed using date + amount pattern matching. Works with most standard bank statement formats. |

All formats are converted to the required JSON schema before being sent to the backend.

---

## Google OAuth

The login page supports **Continue with Google**. To enable it:

1. Go to [Google Cloud Console](https://console.cloud.google.com) → APIs & Services → Credentials
2. Create an **OAuth 2.0 Client ID** (Web application)
3. Add `http://127.0.0.1:8000` to **Authorized JavaScript Origins**
4. Copy the Client ID and replace the placeholder in `luxury-login.html`:

```js
const GOOGLE_CLIENT_ID = 'YOUR_CLIENT_ID.apps.googleusercontent.com';
```

---

## Demo Users

Three pre-built bank datasets are available for testing without uploading:

```bash
# Via API
POST /calculate-trust-score/good_user      # Score ~741, Low Risk
POST /calculate-trust-score/average_user   # Score ~657, Moderate Risk
POST /calculate-trust-score/risky_user     # Score ~518, Very High Risk

# Via Dashboard
Upload tab → "Load Demo Dataset" button
```

---

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `SCORE_ENCRYPTION_KEY` | Recommended | Fernet key for encrypting stored scores. Generate with: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` |
| `GEMINI_API_KEY` | Optional | Google Gemini API key for AI advice and chatbot |
| `GROQ_API_KEY` | Optional | Groq API key (free tier) — fallback if Gemini is unavailable |

If no `SCORE_ENCRYPTION_KEY` is set, a stable default key is used — the app always starts.

---

## Frontend Pages

| Page | URL | Purpose |
|---|---|---|
| Landing | `http://127.0.0.1:8000/` | Introduction and CTA |
| Login | `http://127.0.0.1:8000/luxury-login.html` | Register / Sign in / Google OAuth |
| Dashboard | `http://127.0.0.1:8000/dashboard.html` | All features |

### Dashboard Tabs

| Tab | What it does |
|---|---|
| **Dashboard** | Shows trust score ring, loan eligibility, score breakdown donut, AI recommendations |
| **Analytics** | Radar chart of score dimensions vs benchmark, insights list — all from real backend data |
| **Simulator** | Adjust lifestyle/investment sliders, see real-time score impact via API |
| **Upload** | Upload JSON/CSV/PDF, configure financial inputs, generate trust score |
| **History** | View all saved score reports (requires login) |
| **Advisor** | AI chatbot — ask any financial question, gets personalised answers if score exists |

---

## Licence

Built for hackathon demonstration purposes.
