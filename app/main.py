"""FastAPI app entrypoint."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import Base, engine
from app.models import Profile, Holding, WatchlistItem  # noqa: F401 — ensure models registered
from app.routes.auth import router as auth_router
from app.routes.heatmap import router as heatmap_router
from app.routes.stocks import router as stocks_router
from app.routes.portfolio import router as portfolio_router
from app.routes.watchlist import router as watchlist_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Create database tables on startup."""
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(title="Stockvisor API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(heatmap_router)
app.include_router(stocks_router)
app.include_router(portfolio_router)
app.include_router(watchlist_router)


@app.get("/")
def root():
	return {"status": "ok"}
