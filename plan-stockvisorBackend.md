# Plan: FastAPI Backend with PostgreSQL for Stockvisor MVP

**TL;DR:** Create a separate `stockvisor-backend` folder alongside the frontend with FastAPI, PostgreSQL, and SQLAlchemy. The frontend auth system (Login page, Register page, AuthContext, Axios API service, ProtectedRoute) is **already built and awaiting a live backend**.  Browsing the site no longer requires authentication – the guard is triggered only when the user chooses to log in via the account menu or tries to add a stock from their portfolio. Priority is standing up the auth, portfolio, and stock-data endpoints so the frontend can drop its hardcoded data.

---

## Current Frontend State (as of Feb 2026)

### Tech Stack
- React 19 + React Router DOM 7 + Vite
- Tailwind CSS v4 (explicit green theme `#2ebd85`)
- Axios 1.13.5 — **wired up** via `src/services/api.js`
- Chart.js / react-chartjs-2, lucide-react, react-icons

### What Has Been Built (frontend)

| File | Status |
|------|--------|
| `src/services/api.js` | ✅ Axios instance → `VITE_API_URL` or `http://localhost:8000`; auto-attaches JWT from `localStorage`; auto-redirects on 401 |
| `src/context/AuthContext.jsx` | ✅ `AuthProvider`, `login()`, `register()`, `logout()`, `isAuthenticated`; user state persisted to `localStorage` |
| `src/hooks/useAuth.jsx` | ✅ Re-exports `useAuth` from context |
| `src/pages/Login.jsx` | ✅ Email + password form, error banner, spinner, links to `/register` |
| `src/pages/Register.jsx` | ✅ Username + email + password + confirm, client-side validation, links to `/login` |
| `src/components/ProtectedRoute.jsx` | ✅ Redirects unauthenticated users to `/login`; shows spinner while auth loads |
| `src/App.jsx` | ✅ `/login` and `/register` are public; other pages are freely browsable. Auth is only enforced when a user clicks the login link in the account menu or taps **Add Stock** on Portfolio (redirects to `/login`). |
| `src/main.jsx` | ✅ `<AuthProvider>` wraps the entire app |
| `src/components/Layout.jsx` | ✅ Shows user avatar initial + username/email in dropdown; `logout()` navigates to `/login` |

### Pages & Data Status

| Page | Current Data | Backend Priority |
|------|-------------|-----------------|
| **Home** | Hardcoded 6 stocks | High — stock quotes + user watchlist |
| **Portfolio** | Hardcoded 4 holdings, local add/remove | High — persisted holdings + prices |
| **Community** | Hardcoded discussions + contributors | Medium |
| **News** | Hardcoded articles | Medium |
| **Tips** | Hardcoded educational content | Low (static is fine) |
| **About** | Static page | None |

---

---

## Backend Steps

### 1. Create project structure

Location: `c:\Users\ranwa\Desktop\Uni\FINAL\Ryan Anwar 228939 GP\stockvisor-backend`

```
stockvisor-backend/
├── app/
│   ├── main.py
│   ├── database.py
│   ├── models/
│   │   ├── __init__.py
│   │   ├── user.py
│   │   ├── portfolio.py
│   │   └── watchlist.py
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── auth.py
│   │   ├── portfolio.py
│   │   └── stocks.py
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── auth.py
│   │   ├── portfolio.py
│   │   ├── stocks.py
│   │   └── watchlist.py
│   └── core/
│       ├── config.py
│       └── security.py
├── tests/
├── .env
├── .env.example
└── requirements.txt
```

`requirements.txt`:
```
fastapi
uvicorn[standard]
sqlalchemy
psycopg2-binary
pydantic[email]
pydantic-settings
python-jose[cryptography]
passlib[bcrypt]
python-multipart
python-dotenv
```

---

### 2. Database layer

- `app/database.py` — SQLAlchemy engine from `DATABASE_URL` env var, `SessionLocal`, `Base`
- `app/models/user.py` — `User`: `id`, `username`, `email`, `hashed_password`, `created_at`
- `app/models/portfolio.py` — `Holding`: `id`, `user_id (FK)`, `symbol`, `name`, `quantity`, `purchase_price`, `created_at`
- `app/models/watchlist.py` — `WatchlistItem`: `id`, `user_id (FK)`, `symbol`, `added_at`

---

### 3. Auth system — must match frontend contract exactly

The frontend (`AuthContext.jsx`) calls these endpoints with these exact shapes:

#### `POST /auth/register`
- **Body (JSON):** `{ "username": str, "email": str, "password": str }`
- **Response:** `{ "access_token": str, "token_type": "bearer", "user": { "id": int, "username": str, "email": str } }`

#### `POST /auth/login`
- **Body (form-encoded / `OAuth2PasswordRequestForm`):** `username=<email>&password=<password>`
  > The frontend sends the `username` field containing the user's **email**. FastAPI's `OAuth2PasswordRequestForm` uses `username` by convention.
- **Response:** `{ "access_token": str, "token_type": "bearer", "user": { "id": int, "username": str, "email": str } }`

#### Implementation files:
- `app/core/config.py` — `SECRET_KEY`, `ALGORITHM = "HS256"`, `ACCESS_TOKEN_EXPIRE_MINUTES = 60`
- `app/core/security.py` — `hash_password()`, `verify_password()`, `create_access_token()`, `get_current_user()` dependency
- `app/schemas/auth.py` — `UserCreate`, `Token`, `UserOut` Pydantic models
- `app/routes/auth.py` — `/auth/register` and `/auth/login` endpoints

---

### 4. Portfolio endpoints

Frontend `Portfolio.jsx` currently uses local React state. Replace with API calls once these endpoints exist.

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/portfolio/` | Return all holdings for the authenticated user (merged with live prices) |
| `POST` | `/portfolio/` | Add a holding: `{ symbol, name, quantity, purchase_price }` |
| `DELETE` | `/portfolio/{holding_id}` | Remove a holding (must belong to current user) |

Expected GET response item shape (matches frontend `holdings` state):
```json
{
  "id": "1",
  "symbol": "AAPL",
  "name": "Apple Inc.",
  "quantity": 50,
  "purchasePrice": 150.00,
  "currentPrice": 178.45,
  "dailyChange": 2.34,
  "dailyChangePercent": 1.33
}
```
> `currentPrice`, `dailyChange`, `dailyChangePercent` are injected by the portfolio endpoint from the stock quotes data before returning.

---

### 5. Stock data endpoint (mock, real-API-ready)

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/stocks/quote/{symbol}` | Return price data for a symbol |
| `GET` | `/stocks/search?q={query}` | Search stocks by symbol or name |

Expected quote response:
```json
{
  "symbol": "AAPL",
  "name": "Apple Inc.",
  "price": 178.45,
  "change": 2.34,
  "changePercent": 1.33,
  "volume": "52.3M"
}
```

Start with a `MOCK_PRICES` dict in `app/routes/stocks.py`. To add a real data source later (Alpha Vantage / Polygon.io), only the internal implementation changes — the response shape stays fixed.

---

### 6. Watchlist endpoint

The Home page's starred favorites should persist per-user via this API.

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/watchlist/` | Get authenticated user's watchlist symbols |
| `POST` | `/watchlist/` | Add `{ "symbol": str }` |
| `DELETE` | `/watchlist/{symbol}` | Remove symbol |

---

### 7. CORS (`app/main.py`)

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

---

### 8. Environment variables (`.env`)

```env
DATABASE_URL=postgresql://postgres:yourpassword@localhost:5432/stockvisor
SECRET_KEY=your-256-bit-secret-here
ACCESS_TOKEN_EXPIRE_MINUTES=60
```

Add `.env.example` with placeholder values. Add `.env` to `.gitignore`.

Frontend `.env` (in `stockvisor-frontend/`):
```env
VITE_API_URL=http://localhost:8000
```

---

### 9. Frontend API integration (after backend is running)

| File | Change needed |
|------|--------------|
| `src/services/portfolioService.js` | `getPortfolio()`, `addHolding()`, `removeHolding()` via `api.js` |
| `src/services/stockService.js` | `getQuote(symbol)`, `searchStocks(query)` |
| `src/services/watchlistService.js` | `getWatchlist()`, `addToWatchlist(symbol)`, `removeFromWatchlist(symbol)` |
| `src/pages/Portfolio.jsx` | Replace `useState` hardcoded data with `useEffect` + `portfolioService` |
| `src/pages/Home.jsx` | Replace hardcoded stocks with `stockService`; persist starred via `watchlistService` |

---

## Verification Checklist

```bash
# Backend
cd stockvisor-backend
uvicorn app.main:app --reload       # http://localhost:8000/docs

# Frontend
cd stockvisor-frontend
npm run dev                          # http://localhost:5173
```

- [ ] `POST /auth/register` → returns `{ access_token, user }` → frontend redirects to `/`
- [ ] `POST /auth/login` (form-encoded) → returns `{ access_token, user }` → username appears in nav
- [ ] Any 401 response → frontend clears token and redirects to `/login`
- [ ] `GET /portfolio/` (with `Authorization: Bearer <token>`) → returns user holdings
- [ ] `GET /stocks/quote/AAPL` → returns price object
- [ ] Frontend on `:5173` calls backend on `:8000` without CORS errors
- [ ] FastAPI Swagger: `http://localhost:8000/docs`

---

## Decisions

- **PostgreSQL** for relational auth + portfolio data
- **JWT (HS256)** stateless auth — stored in `localStorage` as `sv_token` + `sv_user`
- **OAuth2PasswordRequestForm** for login — frontend sends `username` field containing the email (FastAPI convention)
- **Mock stock data first**, real API later — response shape is fixed so frontend never changes
- `stockvisor-backend` folder isolated alongside `stockvisor-frontend`
- `sv_token` / `sv_user` localStorage keys namespaced to avoid collisions with other apps