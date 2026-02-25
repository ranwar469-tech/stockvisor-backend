# Stockvisor Backend — Architecture & Flow

## Table of Contents
1. [High-Level Overview](#high-level-overview)
2. [Project Structure](#project-structure)
3. [Configuration & Environment Variables](#configuration--environment-variables)
4. [Application Startup Flow](#application-startup-flow)
5. [Database Layer](#database-layer)
6. [Authentication Flow](#authentication-flow)
7. [Protected Route Flow](#protected-route-flow)
8. [Stock Data Flow](#stock-data-flow)
9. [How Supabase Fits In](#how-supabase-fits-in)
10. [End-to-End Walkthrough](#end-to-end-walkthrough)

---

## High-Level Overview

```
┌─────────────┐         ┌──────────────────┐         ┌─────────────────────┐
│   Frontend   │ ──────▸ │  FastAPI Backend  │ ──────▸ │  Supabase (Cloud)   │
│  (React)     │ ◂────── │  localhost:8000   │ ◂────── │                     │
│  :5173       │         │                  │         │  ┌───────────────┐  │
│              │         │  Routes:         │         │  │ GoTrue Auth   │  │
│              │         │   /auth/*        │────────▸│  │ (signup/login)│  │
│              │         │   /stocks/*      │         │  └───────────────┘  │
│              │         │   /portfolio/*   │         │  ┌───────────────┐  │
│              │         │   /watchlist/*   │────────▸│  │ PostgreSQL DB │  │
│              │         │   /api/heatmap   │         │  │ (profiles,    │  │
│              │         │                  │         │  │  holdings,    │  │
│              │         │                  │         │  │  watchlist)   │  │
└─────────────┘         └──────────────────┘         │  └───────────────┘  │
                                                      └─────────────────────┘
```

**The backend does two things:**
1. **Proxies authentication** — Register/login requests are forwarded to Supabase's GoTrue auth service. Supabase handles password hashing, storage, and JWT issuance. The backend never sees or stores passwords.
2. **Manages application data** — Portfolio holdings, watchlist items, and user profiles are stored in Supabase's PostgreSQL database. The backend connects directly to this database via SQLAlchemy.

---

## Project Structure

```
stockvisor-backend/
├── .env                    ← Your Supabase credentials (not committed)
├── .env.example            ← Template for .env
├── requirements.txt        ← Python dependencies
├── app/
│   ├── main.py             ← FastAPI app entrypoint (creates app, wires routers)
│   ├── database.py         ← SQLAlchemy engine, session, Base
│   ├── core/
│   │   ├── config.py       ← Settings class (reads .env)
│   │   └── security.py     ← JWT validation, get_current_user dependency
│   ├── models/
│   │   ├── __init__.py     ← Re-exports all ORM models
│   │   ├── user.py         ← Profile model (profiles table)
│   │   ├── portfolio.py    ← Holding model (holdings table)
│   │   └── watchlist.py    ← WatchlistItem model (watchlist_items table)
│   ├── schemas/
│   │   ├── auth.py         ← Pydantic schemas for auth requests/responses
│   │   ├── portfolio.py    ← Pydantic schemas for portfolio
│   │   └── stocks.py       ← Pydantic schemas for stock data
│   └── routes/
│       ├── auth.py         ← POST /auth/register, POST /auth/login, GET /auth/me
│       ├── stocks.py       ← GET /stocks/quote/{symbol}, GET /stocks/search
│       ├── heatmap.py      ← GET /api/heatmap
│       ├── portfolio.py    ← CRUD for portfolio holdings (to be built)
│       └── watchlist.py    ← CRUD for watchlist items (to be built)
```

---

## Configuration & Environment Variables

When the app starts, `app/core/config.py` loads 4 environment variables from `.env`:

```
DATABASE_URL=postgresql://postgres.xxxx:password@aws-0-region.pooler.supabase.com:5432/postgres
SUPABASE_URL=https://xxxx.supabase.co
SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIs...
SUPABASE_JWT_SECRET=your-jwt-secret-from-dashboard
```

| Variable | Where It's Used | Where to Find It |
|----------|----------------|-------------------|
| `DATABASE_URL` | `app/database.py` — SQLAlchemy connects to the PostgreSQL database | Supabase Dashboard → Settings → Database → Connection string (URI) |
| `SUPABASE_URL` | `app/routes/auth.py` — Base URL for GoTrue API calls | Supabase Dashboard → Settings → API → Project URL |
| `SUPABASE_ANON_KEY` | `app/routes/auth.py` — Sent as `apikey` header in GoTrue requests | Supabase Dashboard → Settings → API → `anon` `public` key |
| `SUPABASE_JWT_SECRET` | `app/core/security.py` — Used to verify Supabase-issued JWTs | Supabase Dashboard → Settings → API → JWT Secret |

**Flow:**
```
.env file
  └──▸ config.py (Settings class reads it via pydantic-settings)
        ├──▸ database.py (uses DATABASE_URL)
        ├──▸ security.py (uses SUPABASE_JWT_SECRET)
        └──▸ routes/auth.py (uses SUPABASE_URL + SUPABASE_ANON_KEY)
```

---

## Application Startup Flow

When you run `uvicorn app.main:app --reload`, here's what happens step by step:

```
1. Python imports app/main.py
   │
2. main.py imports config.py
   │  └──▸ Settings() reads .env → settings object created
   │
3. main.py imports database.py
   │  └──▸ create_engine(settings.DATABASE_URL) → engine connects to Supabase PostgreSQL
   │  └──▸ SessionLocal created (session factory)
   │  └──▸ Base declared (ORM base class)
   │
4. main.py imports models/__init__.py
   │  └──▸ Imports Profile, Holding, WatchlistItem
   │  └──▸ These models register their tables with Base.metadata
   │
5. main.py imports routers (auth, stocks, heatmap, portfolio, watchlist)
   │
6. FastAPI app is created
   │  └──▸ CORS middleware added (allows frontend at :5173)
   │  └──▸ All routers are included with their prefixes
   │
7. Lifespan startup event fires
   │  └──▸ Base.metadata.create_all(bind=engine)
   │  └──▸ SQLAlchemy inspects the Supabase PostgreSQL database
   │  └──▸ If tables don't exist → CREATE TABLE profiles, holdings, watchlist_items
   │  └──▸ If tables already exist → no-op (safe to restart)
   │
8. Uvicorn starts listening on http://localhost:8000
   └──▸ Ready to accept requests
```

**On first ever startup**, the three tables are created in Supabase's PostgreSQL database automatically. You can see them in the Supabase Dashboard under **Table Editor** in the `public` schema.

---

## Database Layer

### Connection Chain

```
FastAPI route handler
  │
  ▼
get_db() dependency (app/database.py)
  │  Creates a new SQLAlchemy Session from SessionLocal
  │  Yields it to the route handler
  │
  ▼
Route handler uses db.query(...), db.add(...), db.commit(...)
  │
  ▼
SQLAlchemy sends SQL over the network to Supabase PostgreSQL
  │  (using the DATABASE_URL connection string with SSL)
  │
  ▼
Supabase PostgreSQL executes the query and returns results
  │
  ▼
get_db() finally block closes the session
```

### Tables

Three tables live in Supabase PostgreSQL's `public` schema:

```
┌──────────────────┐     ┌──────────────────┐     ┌──────────────────────┐
│     profiles     │     │     holdings      │     │   watchlist_items    │
├──────────────────┤     ├──────────────────┤     ├──────────────────────┤
│ id (PK, UUID str)│◂────│ user_id (FK)     │     │ user_id (FK)        │──▸ profiles.id
│ username         │     │ id (PK, int)     │     │ id (PK, int)         │
│ email            │     │ symbol           │     │ symbol               │
│ created_at       │     │ name             │     │ added_at             │
│                  │     │ quantity         │     │                      │
│                  │     │ purchase_price   │     │ UNIQUE(user_id,      │
│                  │     │ created_at       │     │        symbol)       │
│                  │     │ UNIQUE(user_id,  │     └──────────────────────┘
│                  │     │        symbol)   │
└──────────────────┘     └──────────────────┘
```

**Important:** The `profiles.id` column stores the **same UUID** that Supabase Auth assigns to the user in `auth.users`. This links the Supabase Auth user to our application data. There's no database-level foreign key to `auth.users` because that table lives in Supabase's `auth` schema which SQLAlchemy's `create_all()` can't reference.

### Relationship Between Supabase Auth and Our Tables

```
Supabase-managed (auth schema)          Our tables (public schema)
┌─────────────────────────┐             ┌──────────────────┐
│      auth.users         │             │     profiles     │
├─────────────────────────┤             ├──────────────────┤
│ id: uuid ───────────────│────────────▸│ id: same uuid    │
│ email                   │             │ username         │
│ encrypted_password      │             │ email (copy)     │
│ created_at              │             │ created_at       │
│ ...other auth fields    │             └──────────────────┘
└─────────────────────────┘
      ▲                                         ▲
      │ Supabase manages this                   │ Our backend manages this
      │ (passwords, sessions, JWTs)             │ (display name, app data)
```

---

## Authentication Flow

### Registration: `POST /auth/register`

```
Frontend                    FastAPI Backend                 Supabase GoTrue              Supabase PostgreSQL
   │                              │                              │                              │
   │  POST /auth/register         │                              │                              │
   │  {username, email, password} │                              │                              │
   │─────────────────────────────▸│                              │                              │
   │                              │                              │                              │
   │                              │  POST /auth/v1/signup        │                              │
   │                              │  Headers: apikey=ANON_KEY    │                              │
   │                              │  Body: {email, password,     │                              │
   │                              │         data:{username}}     │                              │
   │                              │─────────────────────────────▸│                              │
   │                              │                              │                              │
   │                              │                              │  Creates row in auth.users   │
   │                              │                              │  Hashes password (bcrypt)    │
   │                              │                              │  Generates UUID              │
   │                              │                              │  Signs JWT with JWT_SECRET   │
   │                              │                              │                              │
   │                              │  Response: {access_token,    │                              │
   │                              │   user: {id: uuid, email}}   │                              │
   │                              │◂─────────────────────────────│                              │
   │                              │                              │                              │
   │                              │  INSERT INTO profiles        │                              │
   │                              │  (id=uuid, username, email)  │                              │
   │                              │─────────────────────────────────────────────────────────────▸│
   │                              │                              │                              │
   │                              │  Row created ◂──────────────────────────────────────────────│
   │                              │                              │                              │
   │  Response: {access_token,    │                              │                              │
   │   token_type: "bearer",      │                              │                              │
   │   user: {id, username, email}│                              │                              │
   │◂─────────────────────────────│                              │                              │
   │                              │                              │                              │
   │  Stores token in localStorage│                              │                              │
```

**What happens to the password:**
1. Frontend sends the raw password to our backend
2. Our backend forwards it to Supabase GoTrue over HTTPS
3. Supabase hashes it with bcrypt and stores it in `auth.users.encrypted_password`
4. **Our backend never stores the password** — no password column in `profiles`

### Login: `POST /auth/login`

```
Frontend                    FastAPI Backend                 Supabase GoTrue
   │                              │                              │
   │  POST /auth/login            │                              │
   │  {email, password}           │                              │
   │─────────────────────────────▸│                              │
   │                              │                              │
   │                              │  POST /auth/v1/token         │
   │                              │  ?grant_type=password        │
   │                              │  Headers: apikey=ANON_KEY    │
   │                              │  Body: {email, password}     │
   │                              │─────────────────────────────▸│
   │                              │                              │
   │                              │                              │  Looks up user by email
   │                              │                              │  Verifies password (bcrypt)
   │                              │                              │  Signs new JWT
   │                              │                              │
   │                              │  Response: {access_token,    │
   │                              │   user: {id: uuid}}          │
   │                              │◂─────────────────────────────│
   │                              │                              │
   │                              │  Looks up Profile by UUID    │
   │                              │  (creates if missing)        │
   │                              │                              │
   │  Response: {access_token,    │                              │
   │   token_type: "bearer",      │                              │
   │   user: {id, username, email}│                              │
   │◂─────────────────────────────│                              │
```

### JWT Structure

The `access_token` returned by Supabase is a standard JWT with this payload:

```json
{
  "sub": "a1b2c3d4-e5f6-...",   ← Supabase user UUID
  "email": "user@example.com",
  "role": "authenticated",
  "aud": "authenticated",
  "exp": 1740525600,             ← Expiry timestamp (Supabase controls this)
  "iat": 1740522000              ← Issued-at timestamp
}
```

It's signed with the `SUPABASE_JWT_SECRET` using HS256. Our backend can verify it without calling Supabase again.

---

## Protected Route Flow

Any route that needs to know "who is this user?" uses the `get_current_user` dependency.

```
Frontend                        FastAPI Backend
   │                                  │
   │  GET /portfolio/                 │
   │  Headers:                        │
   │    Authorization: Bearer eyJ...  │
   │─────────────────────────────────▸│
   │                                  │
   │                    ┌─────────────┴──────────────┐
   │                    │  get_current_user()         │
   │                    │                             │
   │                    │  1. Extract token from       │
   │                    │     Authorization header     │
   │                    │                             │
   │                    │  2. Decode JWT using         │
   │                    │     SUPABASE_JWT_SECRET      │
   │                    │     (no network call!)       │
   │                    │                             │
   │                    │  3. Extract "sub" claim      │
   │                    │     → user UUID              │
   │                    │                             │
   │                    │  4. Query DB:                │
   │                    │     SELECT * FROM profiles   │
   │                    │     WHERE id = uuid          │
   │                    │                             │
   │                    │  5. Return Profile object    │
   │                    │     (or 401 if not found)    │
   │                    └─────────────┬──────────────┘
   │                                  │
   │                    Route handler runs with        │
   │                    current_user = Profile(...)    │
   │                                  │
   │  Response: [{symbol, quantity, ...}]             │
   │◂─────────────────────────────────│
```

**Key insight:** JWT verification is done **locally** using the shared secret — no round-trip to Supabase. This makes protected routes fast.

---

## Stock Data Flow

Stock routes (`/stocks/*` and `/api/heatmap`) don't touch Supabase at all. They use the **yfinance** library to fetch data directly from Yahoo Finance:

```
Frontend                    FastAPI Backend                 Yahoo Finance
   │                              │                              │
   │  GET /stocks/quote/AAPL      │                              │
   │─────────────────────────────▸│                              │
   │                              │  yfinance.Ticker("AAPL")    │
   │                              │  .info / .fast_info          │
   │                              │─────────────────────────────▸│
   │                              │                              │
   │                              │  {price, change, volume...} │
   │                              │◂─────────────────────────────│
   │                              │                              │
   │  {symbol, name, price,       │                              │
   │   change, changePercent,     │                              │
   │   volume}                    │                              │
   │◂─────────────────────────────│                              │
```

These routes are **public** — no authentication required.

---

## How Supabase Fits In

Supabase provides **two separate services** that this backend uses:

### Service 1: GoTrue Auth (Authentication)

- **What it does:** Stores user credentials, hashes passwords, issues JWTs
- **How we use it:** The backend makes HTTP calls to `{SUPABASE_URL}/auth/v1/signup` and `{SUPABASE_URL}/auth/v1/token` using `httpx`
- **Identified by:** `SUPABASE_URL` + `SUPABASE_ANON_KEY` (sent as `apikey` header)
- **Where passwords live:** In Supabase's `auth.users` table (we never see or store them)

### Service 2: PostgreSQL Database (Data Storage)

- **What it does:** Stores our application tables (`profiles`, `holdings`, `watchlist_items`)
- **How we use it:** SQLAlchemy connects directly via the `DATABASE_URL` connection string
- **Identified by:** `DATABASE_URL` (includes host, port, user, password, database name)
- **What lives here:** User profiles, portfolio holdings, watchlist items

```
Supabase Project
├── Auth Service (GoTrue)
│   ├── Handles: signup, login, password reset
│   ├── Stores: auth.users (email, hashed password, UUID)
│   ├── Issues: JWT tokens signed with JWT_SECRET
│   └── Accessed via: HTTPS REST API (SUPABASE_URL + ANON_KEY)
│
├── PostgreSQL Database
│   ├── auth schema (Supabase-managed, don't touch)
│   │   └── auth.users
│   ├── public schema (our tables)
│   │   ├── profiles (id=UUID, username, email)
│   │   ├── holdings (user_id → profiles.id)
│   │   └── watchlist_items (user_id → profiles.id)
│   └── Accessed via: Direct PostgreSQL connection (DATABASE_URL)
│
└── JWT Secret
    └── Shared secret used by GoTrue to sign tokens
        and by our backend to verify them
```

---

## End-to-End Walkthrough

### Scenario: New user registers, then views their empty portfolio

**Step 1: User fills in the registration form and clicks "Register"**

```
Frontend sends:
  POST http://localhost:8000/auth/register
  Content-Type: application/json
  Body: {"username": "ryan", "email": "ryan@test.com", "password": "mypass123"}
```

**Step 2: Backend receives the request in `app/routes/auth.py`**

```python
# The route handler does this:
async with httpx.AsyncClient() as client:
    response = await client.post(
        f"{settings.SUPABASE_URL}/auth/v1/signup",
        headers={"apikey": settings.SUPABASE_ANON_KEY},
        json={"email": "ryan@test.com", "password": "mypass123",
              "data": {"username": "ryan"}}
    )
```

**Step 3: Supabase GoTrue processes the signup**

- Creates a new row in `auth.users` with a UUID like `a1b2c3d4-...`
- Hashes `mypass123` with bcrypt → stores the hash
- Signs a JWT containing `{"sub": "a1b2c3d4-...", "email": "ryan@test.com", ...}`
- Returns the JWT + user info to our backend

**Step 4: Backend creates the profile**

```python
# Backend extracts the UUID and creates a profile row:
profile = Profile(id="a1b2c3d4-...", username="ryan", email="ryan@test.com")
db.add(profile)
db.commit()
```

This INSERT goes directly to Supabase PostgreSQL via SQLAlchemy.

**Step 5: Backend returns the token to the frontend**

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer",
  "user": {"id": "a1b2c3d4-...", "username": "ryan", "email": "ryan@test.com"}
}
```

**Step 6: Frontend stores the token and navigates to the portfolio page**

```
Frontend sends:
  GET http://localhost:8000/portfolio/
  Authorization: Bearer eyJhbGciOiJIUzI1NiIs...
```

**Step 7: Backend validates the token (no network call to Supabase)**

```python
# security.py does this:
payload = jwt.decode(token, settings.SUPABASE_JWT_SECRET, algorithms=["HS256"])
user_id = payload["sub"]  # "a1b2c3d4-..."
profile = db.query(Profile).filter(Profile.id == user_id).first()
# Returns the Profile object to the route handler
```

**Step 8: Route handler queries holdings for this user**

```python
holdings = db.query(Holding).filter(Holding.user_id == current_user.id).all()
# Returns [] (empty list, new user)
```

**Step 9: Frontend displays an empty portfolio**

---

## After Adding Supabase API Keys

Once you create a Supabase project and fill in the `.env` file:

1. **`uvicorn app.main:app --reload`** starts the server
2. **On startup**, SQLAlchemy connects to Supabase PostgreSQL using `DATABASE_URL` and runs `CREATE TABLE IF NOT EXISTS` for `profiles`, `holdings`, and `watchlist_items`
3. **Registration/Login** works immediately — the backend proxies to Supabase GoTrue using `SUPABASE_URL` and `SUPABASE_ANON_KEY`
4. **Token verification** works immediately — the backend decodes JWTs using `SUPABASE_JWT_SECRET` (the same secret Supabase used to sign the token)
5. **No Supabase Dashboard configuration needed** beyond copying the 4 values — no Row Level Security policies, no edge functions, no Supabase client SDK

The entire auth + database infrastructure is **cloud-hosted by Supabase** (free tier). The FastAPI backend is the only thing running locally.