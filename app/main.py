"""FastAPI app entrypoint."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import inspect, text

from app.database import Base, engine
from app.models import Profile, Holding, WatchlistItem, SavedNews, Thread, Post  # noqa: F401 — ensure models registered
from app.routes.auth import router as auth_router
from app.routes.heatmap import router as heatmap_router
from app.routes.stocks import router as stocks_router
from app.routes.portfolio import router as portfolio_router
from app.routes.watchlist import router as watchlist_router
from app.routes.insights import router as insights_router
from app.routes.discussions import router as discussions_router
from app.routes.admin import router as admin_router


def ensure_profile_role_column() -> None:
    """Ensure profiles.role column exists for deployments with older schemas."""
    inspector = inspect(engine)
    if "profiles" not in inspector.get_table_names():
        return

    column_names = {col["name"] for col in inspector.get_columns("profiles")}

    with engine.begin() as conn:
        if "role" not in column_names:
            conn.execute(text("ALTER TABLE profiles ADD COLUMN role VARCHAR(20)"))


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Create database tables on startup."""
    Base.metadata.create_all(bind=engine)
    ensure_profile_role_column()
    yield


app = FastAPI(title="Stockvisor API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(heatmap_router)
app.include_router(stocks_router)
app.include_router(portfolio_router)
app.include_router(watchlist_router)
app.include_router(insights_router)
app.include_router(discussions_router)
app.include_router(admin_router)


@app.get("/")
def root():
	return {"status": "ok"}
