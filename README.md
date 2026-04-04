# 🚀 TrustMetric —  Financial Trust Score System

> A full-stack AI-powered financial trust scoring platform built for individuals without traditional credit histories.

---

## 📌 What It Does

TrustMetric calculates a **financial trust score (300–900)** based on real transaction behaviour — not just credit history.

It analyses how people actually **spend, save, and pay bills** to generate a **transparent, explainable financial identity score**.

---

## 🚀 Live Demo

🔗 **Demo:** https://trustmetric.onrender.com

### Demo Credentials (Optional)
Email: demo@trustmetric.com  
Password: demo123

> ⚡ Tip: Use built-in demo datasets (good / average / risky) for quick testing.

---

## ✨ Key Features

- 📊 Trust score calculation from real transaction data  
- 💸 Micro-loan eligibility recommendation  
- 🔮 What-if score simulator  
- 🤖 AI financial advisor chatbot (Gemini + Groq)  
- 🔐 Secure encrypted score history  
- 📂 File upload support — JSON, CSV, PDF bank statements  

---

## 🧠 How the Score Works

TrustMetric evaluates users across **5 core financial dimensions**:

| Dimension | Description | Weight |
|----------|------------|--------|
| Liquidity | Income vs expenses ratio | 25% |
| Discipline | Bills paid on time | 25% |
| Stability | Spending consistency | 20% |
| Asset Protection | Savings + insurance | 15% |
| Risk | Lifestyle spending behavior | 15% |

### 📐 Score Formula

raw_score = (0.25 × liquidity) + (0.25 × discipline) + (0.20 × stability)  
          + (0.15 × asset_protection) + (0.15 × risk)  

trust_score = 300 + (raw_score / 100) × 600

---

## 💰 Loan Eligibility Logic

surplus            = income − expenses  
repayment_capacity = surplus × 0.4  
risk_factor        = trust_score / 900  

recommended_loan   = repayment_capacity × risk_factor × 12  

- Range: ₹5,000 – ₹50,000  
- Reliability Score = Trust (50%) + Discipline (30%) + Stability (20%)

---

## 🔮 Score Simulator

POST /simulate-score

{
  "simulation_changes": {
    "reduce_lifestyle_spending_percent": 20,
    "increase_investment_percent": 15
  }
}

---

## 📂 File Upload Support

| Format | Processing |
|-------|-----------|
| JSON | Direct parsing |
| CSV | PapaParse |
| PDF | PDF.js |

---

## 🛠 Tech Stack

| Layer | Technology |
|------|-----------|
| Backend | Python 3.12, FastAPI, Uvicorn |
| Frontend | HTML, CSS, JavaScript, Chart.js, WebGL |
| Database | SQLite |
| Security | SHA-256, PBKDF2-HMAC-SHA256, Fernet Encryption |
| AI | Google Gemini, Groq (LLaMA3-70B) |
| Parsing | PDF.js, PapaParse |

---

## 📁 Project Structure

TrustMetric/
│
├── main.py
├── trust_score_engine.py
├── transaction_cleaner.py
├── score_explainer.py
├── advisor_engine.py
├── ai_chatbot.py
├── loan_engine.py
├── score_simulator.py
├── data_validator.py
├── bank_connector.py
│
├── database.py
├── security.py
│
├── landing.html
├── luxury-login.html
├── dashboard.html
│
├── .env.example
├── trust_score.db
│
└── bank_data/
    ├── good_user.json
    ├── average_user.json
    └── risky_user.json

---

## ⚡ Quick Start

pip install fastapi uvicorn python-dotenv cryptography  
uvicorn main:app --reload  

Open: http://127.0.0.1:8000

---

## 🔐 Authentication

POST /register  
POST /login  

Use Header: X-User-ID

---

## 🔒 Security

- SHA-256 (email)  
- PBKDF2-HMAC-SHA256 (password)  
- Fernet encryption (score data)  

---

## 📡 API Endpoints

| Method | Endpoint | Description |
|-------|--------|------------|
| GET | / | Landing page |
| GET | /dashboard.html | Dashboard |
| POST | /register | Register |
| POST | /login | Login |
| POST | /calculate-trust-score | Calculate score |
| POST | /simulate-score | Simulation |
| POST | /financial-chat | AI advisor |
| GET | /my-scores | Score history |

---

## 🧪 Demo Data

POST /calculate-trust-score/good_user  
POST /calculate-trust-score/average_user  
POST /calculate-trust-score/risky_user  

---

## 🌍 Use Cases

- Credit scoring for unbanked users  
- Fintech risk assessment  
- Micro-lending platforms  
- Personal finance insights  
- AI-driven financial advisory  

---

## 📄 License

Built for hackathon demonstration purposes.

---

## ⭐ Future Improvements

- Open banking API integration  
- Real-time bank sync  
- Advanced ML scoring models  
- Mobile app version  
- Blockchain-based identity verification  

---

## 💡 Inspiration

Traditional credit systems exclude millions.  
**TrustMetric redefines trust using behaviour, not history.**
