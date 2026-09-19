# EVGuard — State-Aware Security Gateway for EV Charging Commands

> **Status: DRAFT / MVP Skeleton**

EVGuard is a state-aware pre-execution security gateway for electric vehicle (EV) charging commands. Operating logically between charging controllers and the execution layer, EVGuard deterministically evaluates every incoming command against sender authentication, role authorization, charging session finite state machine (FSM) validity, physical safety limits (independent power and current thresholds), and sender rate limits before any command reaches the charger. Every evaluation produces an explainable ALLOW or BLOCK decision accompanied by a rule ID and human-readable explanation, with all decisions recorded in a secure SQLite audit trail.

---

## Setup & Running (Role 1)

### 1. Prerequisites
- Python 3.12 (`py -3.12`)

### 2. Create and Activate Virtual Environment
```bash
# Windows
py -3.12 -m venv .venv
.venv\Scripts\activate

# macOS / Linux
python3.12 -m venv .venv
source .venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Run API Server (Localhost only)
```bash
uvicorn backend.main:app --host 127.0.0.1 --port 8000
```
Interactive OpenAPI documentation will be accessible at: `http://127.0.0.1:8000/docs`  
Health check endpoint: `http://127.0.0.1:8000/health`

### 5. Run Tests
```bash
pytest -q
```

