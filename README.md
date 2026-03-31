TrustMetric — Alternative Financial Trust Score System

A full-stack AI-powered financial trust scoring platform built for individuals without traditional credit histories. Built for hackathon.

What It Does

TrustMetric calculates a financial trust score (300–900) based on real transaction behaviour — not just credit history. It analyses how people actually spend, save, and pay bills to produce a transparent, explainable financial identity score.

Key capabilities:

Trust score calculation from transaction data
Micro-loan eligibility recommendation
What-if score simulator
AI financial advisor chatbot (Gemini + Groq)
Secure encrypted score history
File upload support — JSON, CSV, PDF bank statements
🚀 Live Demo

Experience TrustMetric in action:

🔗 Demo Link: https://trustmetric.onrender.com/

Demo Credentials (optional):

Email: demo@trustmetric.com
Password: demo123

Try these features in demo:

Upload sample financial data or use demo datasets
View real-time trust score calculation
Test "What-if" simulation
Chat with AI financial advisor
Check loan eligibility instantly

⚡ Tip: Use the built-in demo datasets (good / average / risky) for quick testing.

Tech Stack
Layer	Technology
Backend	Python 3.12, FastAPI, Uvicorn
Frontend	Vanilla HTML/CSS/JS, Chart.js, WebGL
Database	SQLite (via Python sqlite3)
Security	SHA-256 (email), PBKDF2-HMAC-SHA256 (password), Fernet AES-128 (score data)
AI	Google Gemini (primary), Groq llama3-70b (fallback)
PDF Parsing	PDF.js (loaded on demand)
CSV Parsing	PapaParse
Project Structure
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
Quick Start
1. Install dependencies
pip install fastapi uvicorn python-dotenv cryptography
2. Set up environment variables
# Copy the example file
cp .env.example .env

Edit .env:

# Generate this key by running:
# python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
SCORE_ENCRYPTION_KEY=your_generated_key_here

# At least one AI key required for chatbot and financial advice
GEMINI_API_KEY=your_gemini_key
GROQ_API_KEY=your_groq_key

Note: The app starts and all core features work even without a .env file. Only the AI chatbot and financial advice text require an API key.

3. Run the server
uvicorn main:app --reload
4. Open in browser
http://127.0.0.1:8000
API Endpoints
Method	Path	Description
GET	/	Landing page
GET	/luxury-login.html	Login / Register page
GET	/dashboard.html	Main dashboard
POST	/register	Create user account
POST	/login	Login, returns user_id
POST	/calculate-trust-score	Calculate score from uploaded data
POST	/calculate-trust-score/{user_id}	Calculate score from demo bank data
POST	/simulate-score	Simulate score changes
POST	/financial-chat	AI financial advisor chatbot
GET	/my-scores	Retrieve saved score history

Interactive API docs:
http://127.0.0.1:8000/docs

Authentication

Register and login to save your scores across sessions.

POST /register
{ "email": "you@example.com", "password": "yourpassword" }

POST /login
{ "email": "you@example.com", "password": "yourpassword" }

Response:

{ "user_id": 1, "message": "Login successful." }

Include header:

X-User-ID: 1

Security:

Email → SHA-256 hash
Password → PBKDF2-HMAC-SHA256 (260k iterations)
Score → Fernet encryption
Trust Score Input Format
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
    { "date": "2024-01-01", "merchant": "Employer Salary", "amount": 75000, "category": "income" }
  ]
}
How the Score Works

The trust score is calculated across 5 dimensions, each scored 0–100:

Dimension	What it measures	Weight
Liquidity	Income vs expenses	25%
Discipline	Bills paid on time	25%
Stability	Spending consistency	20%
Asset Protection	Savings + insurance	15%
Risk	Lifestyle spending	15%
trust_score = 300 + (raw_score / 100) × 600
Loan Eligibility
recommended_loan = (income − expenses) × 0.4 × (score / 900) × 12

Range: ₹5,000 – ₹50,000

Score Simulator

Test financial changes safely:

POST /simulate-score
{
  "simulation_changes": {
    "reduce_lifestyle_spending_percent": 20
  }
}
File Upload Support
Format	Processing
JSON	Direct
CSV	PapaParse
PDF	PDF.js
Google OAuth

Steps:

Go to Google Cloud Console
Create OAuth Client ID
Add origin
Paste Client ID
Demo Users
POST /calculate-trust-score/good_user
POST /calculate-trust-score/average_user
POST /calculate-trust-score/risky_user
Environment Variables
Variable	Description
SCORE_ENCRYPTION_KEY	Encryption key
GEMINI_API_KEY	AI
GROQ_API_KEY	AI fallback
Frontend Pages
Page	URL
Landing	/
Login	/luxury-login.html
Dashboard	/dashboard.html
