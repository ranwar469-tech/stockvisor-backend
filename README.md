# StockVisor

A full-stack stock market platform built with React 19 + Vite (frontend) and FastAPI (backend). Track portfolios, explore market data, read financial news, participate in community discussions, and get AI-powered insights.

## Project Structure

```
stockvisor-frontend/   ← React + Vite SPA
stockvisor-backend/    ← FastAPI + PostgreSQL API
```

## Prerequisites

- **Node.js** 18+
- **Python** 3.10+
- **Supabase** account (for database + auth)

## Backend Setup

```bash
cd stockvisor-backend

# Create and activate a virtual environment
python -m venv venv
venv\Scripts\activate      # Windows
# source venv/bin/activate  # macOS/Linux

# Install dependencies
pip install -r requirements.txt
```

The `.env` file is already provided with all required credentials.

Start the backend:

```bash
uvicorn app.main:app --reload --port 8000
```

The API runs at `http://localhost:8000`. Swagger docs at `http://localhost:8000/docs`.

## Frontend Setup

```bash
cd stockvisor-frontend

# Install dependencies
npm install

# Start the dev server
npm run dev
```

The app runs at `http://localhost:5173`.

## Quick Start (Both)

```bash
# Terminal 1 — Backend
cd stockvisor-backend
venv\Scripts\activate
uvicorn app.main:app --reload --port 8000

# Terminal 2 — Frontend
cd stockvisor-frontend
npm install
npm run dev
```

## Available Scripts

### Frontend

| Command | Description |
|---|---|
| `npm run dev` | Start Vite dev server |
| `npm test` | Run all tests (single run) |
| `npx vitest run --reporter=verbose` | Run tests with detailed output |

### Backend

| Command | Description |
|---|---|
| `py -m uvicorn app.main:app --reload --port 8000` | Start FastAPI server |
| `py -m pytest -v` | Run all backend tests |
| `py -m locust -f tests/locustfile.py` | Run Locust load test (web UI) |


## Tech Stack

**Frontend:** React 19, Vite, Tailwind CSS v4, React Router, Chart.js + Recharts, Axios

**Backend:** FastAPI, SQLAlchemy, Supabase (PostgreSQL + Auth), yFinance, Finnhub, Hugging Face Inference API
