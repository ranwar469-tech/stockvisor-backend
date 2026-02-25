# Stockvisor FastAPI Backend — Implementation Roadmap

**TL;DR:** Authentication is handled by **Supabase Auth (GoTrue)** — the FastAPI backend proxies register/login calls to Supabase's REST API and returns Supabase-issued JWTs to the frontend. Protected endpoints validate those JWTs server-side using the project's JWT secret. User profile data lives in a `profiles` table (public schema) keyed by UUID from Supabase's `auth.users`. The database is hosted on **Supabase PostgreSQL**. Stock data routes (quotes, search, heatmap) use yfinance and are already implemented.

---

## What's Done (Phase 0) ✅

| Item | Status |
|------|--------|
| Project folder structure (`app/`, `models/`, `schemas/`, `routes/`, `core/`, `tests/`) | ✅ Created |
| `requirements.txt` with all dependencies | ✅ Created |
| `.env.example` with Supabase template variables | ✅ Created |
| `.gitignore` (`.env`, `__pycache__/`, `venv/`, `*.pyc`) | ✅ Created |
| `maintest.py` — standalone yfinance proof-of-concept | ✅ Exists (pre-existing) |
| `app/routes/stocks.py` — `GET /stocks/quote/{symbol}`, `GET /stocks/search?q=` via yfinance | ✅ Implemented |
| `app/routes/heatmap.py` — `GET /api/heatmap` with 4-sector live data | ✅ Implemented |
| `app/schemas/stocks.py` — `StockQuote`, `StockSearchResult` | ✅ Implemented |

---

## What Needs to Be Built

### Step 1 — Environment & Config (`app/core/config.py`, `.env`) ✅

- Implement a `Settings` class using `pydantic-settings` (`BaseSettings`) that reads from `.env`:
  - `DATABASE_URL` — Supabase PostgreSQL connection string (Dashboard → Settings → Database → Connection string URI, Session mode / port 5432)
  - `SUPABASE_URL` — project URL, e.g. `https://xyzxyz.supabase.co`
  - `SUPABASE_ANON_KEY` — anon/public API key (Dashboard → Settings → API)
  - `SUPABASE_JWT_SECRET` — JWT secret for verifying Supabase-issued tokens (Dashboard → Settings → API → JWT Secret)
- Export a singleton `settings = Settings()` for import elsewhere
- **Removed:** `SECRET_KEY` and `ACCESS_TOKEN_EXPIRE_MINUTES` (Supabase controls token signing & lifespan)

### Step 2 — Database Layer (`app/database.py`) ✅

- Create SQLAlchemy `engine` from `settings.DATABASE_URL`
- Create `SessionLocal` sessionmaker
- Declare `Base = declarative_base()`
- Write `get_db()` generator dependency (yields session, closes on teardown)
- Supabase PostgreSQL uses SSL by default; the connection string includes `sslmode=require`

### Step 3 — ORM Models (`app/models/`) ✅

**`app/models/user.py`** — `Profile` table (mapped to `profiles` in public schema):

| Column | Type | Notes |
|--------|------|-------|
| `id` | String (UUID text), PK | Matches `auth.users.id` from Supabase — no FK since `auth` schema is Supabase-managed |
| `username` | String, unique, not null | Display name chosen at registration |
| `email` | String, unique, not null | Mirrored from Supabase `auth.users.email` |
| `created_at` | DateTime, server default `now()` | |

> **Note:** No `hashed_password` column — password storage is fully managed by Supabase Auth.

**`app/models/portfolio.py`** — `Holding` table:

| Column | Type | Notes |
|--------|------|-------|
| `id` | Integer, PK, autoincrement | |
| `user_id` | String, FK → `profiles.id`, not null | UUID text matching Supabase user |
| `symbol` | String(10), not null | e.g. "AAPL" |
| `name` | String(100) | e.g. "Apple Inc." |
| `quantity` | Float, not null | |
| `purchase_price` | Float, not null | |
| `created_at` | DateTime, server default `now()` | |

**`app/models/watchlist.py`** — `WatchlistItem` table:

| Column | Type | Notes |
|--------|------|-------|
| `id` | Integer, PK, autoincrement | |
| `user_id` | String, FK → `profiles.id`, not null | UUID text matching Supabase user |
| `symbol` | String(10), not null | |
| `added_at` | DateTime, server default `now()` | |

- Unique constraint on `(user_id, symbol)` for both `Holding` and `WatchlistItem`
- Re-export all models from `app/models/__init__.py` so `Base.metadata` sees them for `create_all()`

### Step 4 — Security / JWT Validation (`app/core/security.py`) ✅

- **Removed:** `hash_password`, `verify_password`, `create_access_token` — Supabase handles all of this
- `OAuth2PasswordBearer(tokenUrl="/auth/login")` to extract `Authorization: Bearer <token>` header
- `get_current_user(token, db)` dependency:
  1. Decode JWT using `jose.jwt.decode(token, settings.SUPABASE_JWT_SECRET, algorithms=["HS256"], options={"verify_aud": False})`
  2. Extract `sub` claim (Supabase user UUID)
  3. Query `Profile` by `id == sub`
  4. If no profile → raise `HTTPException(401)`
  5. Return the `Profile` object

### Step 5 — Pydantic Schemas (`app/schemas/`) ✅

**`app/schemas/auth.py`:**
- `UserCreate(username: str, email: EmailStr, password: str)` — register request body
- `UserLogin(email: EmailStr, password: str)` — login request body
- `UserOut(id: str, username: str, email: str)` — safe user representation (UUID string, no password)
- `Token(access_token: str, token_type: str, user: UserOut)` — response for both login and register

**`app/schemas/portfolio.py`:**
- `HoldingCreate(symbol, quantity, purchase_price)` — request body (`name` resolved server-side)
- `HoldingResponse(id, symbol, name, quantity, purchasePrice, currentPrice, dailyChange, dailyChangePercent)` — camelCase aliases to match frontend

**`app/schemas/stocks.py`:** *(already implemented)*
- `StockQuote(symbol, name, price, change, changePercent, volume)`
- `StockSearchResult(symbol, name)`

### Step 6 — Auth Routes (`app/routes/auth.py`) ✅

Uses `httpx.AsyncClient` to proxy calls to Supabase GoTrue API.

**`POST /auth/register`** (JSON body: `UserCreate`):
1. Call Supabase: `POST {SUPABASE_URL}/auth/v1/signup` with `apikey` header and `{"email", "password", "data": {"username"}}`
2. On Supabase error (e.g. "User already registered") → raise `400`
3. Extract `user.id` (UUID) and `access_token` from response
4. Create `Profile` row in DB with `id=uuid`, `username`, `email`
5. Return `Token(access_token, token_type="bearer", user=UserOut)`

**`POST /auth/login`** (JSON body: `UserLogin`):
1. Call Supabase: `POST {SUPABASE_URL}/auth/v1/token?grant_type=password` with `apikey` header and `{"email", "password"}`
2. On error → raise `401` with `"Invalid email or password"`
3. Extract `access_token` and user UUID
4. Look up `Profile` by UUID; if missing, create it
5. Return `Token(access_token, token_type="bearer", user=UserOut)`

**`GET /auth/me`** (protected — requires `get_current_user`):
- Return `UserOut` for the authenticated user (frontend uses this to check session)

### Step 7 — Stock Data Routes (`app/routes/stocks.py`) *(already implemented)*

- `GET /stocks/quote/{symbol}` — real-time quote via yfinance
- `GET /stocks/search?q={query}` — search equities via yfinance

### Step 8 — Portfolio Routes (`app/routes/portfolio.py`)

All endpoints require authentication (`get_current_user` dependency).

**`GET /portfolio/`:**
1. Query all `Holding` rows for `current_user.id`
2. For each holding, look up current price from stocks service
3. Compute `dailyChange`, `dailyChangePercent`
4. Return list of `HoldingResponse` with camelCase field aliases

**`POST /portfolio/`:**
1. Accept `HoldingCreate`
2. Resolve `name` from stock data (or leave blank)
3. Insert `Holding`, return `HoldingResponse`

**`DELETE /portfolio/{holding_id}`:**
1. Find holding by ID, verify `user_id == current_user.id`
2. Not found or wrong user → `404`
3. Delete and return `204`

### Step 9 — Watchlist Routes (`app/routes/watchlist.py`)

All endpoints require authentication.

- **`GET /watchlist/`** → list of `{ symbol, addedAt }` for current user
- **`POST /watchlist/`** → add `{ "symbol": "AAPL" }`, duplicate → `409`
- **`DELETE /watchlist/{symbol}`** → remove, not found → `404`

### Step 10 — App Entrypoint (`app/main.py`) ✅

- Create `FastAPI(title="Stockvisor API")`
- Add `CORSMiddleware` allowing `http://localhost:5173`, credentials, all methods/headers
- Include routers: `auth.router` (prefix `/auth`), `portfolio.router` (prefix `/portfolio`), `stocks.router` (prefix `/stocks`), `watchlist.router` (prefix `/watchlist`), `heatmap.router`
- On startup: call `Base.metadata.create_all(bind=engine)` to auto-create tables in Supabase
- Health-check `GET /` → `{ "status": "ok" }`

### Step 11 — Supabase Setup

1. Create a Supabase project at [supabase.com](https://supabase.com)
2. From Dashboard → Settings → Database → Connection string (URI), copy the connection string
3. From Dashboard → Settings → API, copy:
   - Project URL → `SUPABASE_URL`
   - `anon` / `public` key → `SUPABASE_ANON_KEY`
   - JWT Secret → `SUPABASE_JWT_SECRET`
4. Paste all values into `.env` (use `.env.example` as template)
5. Tables (`profiles`, `holdings`, `watchlist_items`) are auto-created by `SQLAlchemy create_all()` on first app startup

### Step 12 — Testing & Verification

Install dependencies: `pip install -r requirements.txt`
Run server: `uvicorn app.main:app --reload`
Verify Swagger UI at `http://localhost:8000/docs`

**Manual test checklist:**
- `POST /auth/register` with `{"username", "email", "password"}` → token + user
- `POST /auth/login` with `{"email", "password"}` → token + user
- `GET /auth/me` with `Authorization: Bearer <token>` → user profile
- `GET /stocks/quote/AAPL` → quote object
- `GET /portfolio/` with Bearer token → empty list
- `POST /portfolio/` → holding created
- `DELETE /portfolio/{id}` → 204
- Verify user appears in Supabase Dashboard → Authentication → Users
- Verify `profiles` table exists in Supabase Dashboard → Table Editor
- Frontend on `:5173` → register → login → no CORS errors → username in nav

### Dependency graph
```
Step 1: config.py + .env (Supabase credentials)
  └──▸ Step 2: database.py (needs DATABASE_URL from config)
        └──▸ Step 3: models (needs Base from database)
              └──▸ Step 4: security.py (validates Supabase JWTs, needs Profile model)
                    └──▸ Step 5: schemas (independent, but referenced by routes)
                          └──▸ Step 6: auth routes (proxies to Supabase GoTrue via httpx)
                          └──▸ Step 7: stocks routes ✅ (already done, no auth needed)
                          └──▸ Step 8: portfolio routes (needs auth + stocks)
                          └──▸ Step 9: watchlist routes (needs auth)
                                └──▸ Step 10: main.py (wires everything)
                                      └──▸ Step 11: Supabase project setup
                                            └──▸ Step 12: verify end-to-end
```

### Key Architecture Decisions

| Decision | Rationale |
|----------|-----------|
| **Supabase Auth (GoTrue)** over custom bcrypt/JWT | Offloads password storage, hashing, and session management to Supabase |
| **Backend-proxied auth** over frontend-direct Supabase | Keeps the same REST API shape; frontend doesn't need `@supabase/supabase-js` |
| **`profiles` table** in public schema linked by UUID | Can't FK to `auth.users` via SQLAlchemy `create_all()`; UUID stored as string |
| **`httpx`** over `supabase-py` client | Lighter dependency; only 2 HTTP calls needed; more transparent |
| **`python-jose`** for JWT validation | Verifies Supabase tokens server-side using `SUPABASE_JWT_SECRET` |