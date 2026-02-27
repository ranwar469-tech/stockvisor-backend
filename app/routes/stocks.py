"""Stock data routes — quotes and search powered by yfinance."""

import math
from typing import List

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, status
import yfinance as yf
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import get_current_user
from app.database import get_db
from app.models.saved_news import SavedNews
from app.models.user import Profile
from app.schemas.stocks import (
    MarketStatus,
    NewsItem,
    SavedNewsCreate,
    SavedNewsResponse,
    StockRecommendation,
    StockQuote,
    StockSearchResult,
)

router = APIRouter(prefix="/stocks", tags=["stocks"])


@router.get("/status",response_model=MarketStatus)
def get_market_status():
    market = yf.Market("US").status
    currentStatus=market["status"]
    return MarketStatus(status=currentStatus)


@router.get("/news", response_model=List[NewsItem])
async def get_market_news(
    category: str = Query("general", min_length=1, description="Finnhub news category"),
):
    """Return market news from Finnhub by category."""
    if not settings.FINNHUB_API_KEY:
        raise HTTPException(
            status_code=503,
            detail="FINNHUB_API_KEY is not configured",
        )

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(
            "https://finnhub.io/api/v1/news",
            params={"category": category, "token": settings.FINNHUB_API_KEY},
        )

    if resp.status_code >= 400:
        raise HTTPException(
            status_code=502,
            detail="Failed to fetch news from Finnhub",
        )

    data = resp.json()
    if not isinstance(data, list):
        raise HTTPException(
            status_code=502,
            detail="Unexpected response from Finnhub",
        )

    return data


@router.get("/recommendations", response_model=StockRecommendation)
async def get_stock_recommendations(
    symbol: str = Query(..., min_length=1, description="Ticker symbol, e.g. AAPL"),
):
    """Return latest analyst recommendation trend for a symbol from Finnhub."""
    if not settings.FINNHUB_API_KEY:
        raise HTTPException(
            status_code=503,
            detail="FINNHUB_API_KEY is not configured",
        )

    normalized_symbol = symbol.upper().strip()

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(
            "https://finnhub.io/api/v1/stock/recommendation",
            params={"symbol": normalized_symbol, "token": settings.FINNHUB_API_KEY},
        )

    if resp.status_code >= 400:
        raise HTTPException(
            status_code=502,
            detail="Failed to fetch recommendations from Finnhub",
        )

    data = resp.json()
    if not isinstance(data, list) or not data:
        raise HTTPException(
            status_code=404,
            detail=f"No recommendations found for symbol '{normalized_symbol}'",
        )

    latest = max(data, key=lambda item: item.get("period") or "")

    return StockRecommendation(
        buy=int(latest.get("buy") or 0),
        hold=int(latest.get("hold") or 0),
        period=str(latest.get("period") or ""),
        sell=int(latest.get("sell") or 0),
        strongBuy=int(latest.get("strongBuy") or 0),
        strongSell=int(latest.get("strongSell") or 0),
        symbol=str(latest.get("symbol") or normalized_symbol),
    )


@router.get("/news/saved", response_model=List[SavedNewsResponse])
def list_saved_news(
    current_user: Profile = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return all saved news articles for the current user."""
    items = (
        db.query(SavedNews)
        .filter(SavedNews.user_id == current_user.id)
        .order_by(SavedNews.saved_at.desc())
        .all()
    )
    return [
        SavedNewsResponse(
            id=item.id,
            external_id=item.external_id,
            category=item.category,
            datetime=item.published_at,
            headline=item.headline,
            image=item.image,
            related=item.related,
            source=item.source,
            summary=item.summary,
            url=item.url,
        )
        for item in items
    ]


@router.post("/news/saved", response_model=SavedNewsResponse, status_code=status.HTTP_201_CREATED)
def save_news_item(
    body: SavedNewsCreate,
    current_user: Profile = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Save a news article for the current user. 409 if already saved."""
    existing = (
        db.query(SavedNews)
        .filter(
            SavedNews.user_id == current_user.id,
            SavedNews.external_id == body.external_id,
        )
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This news article is already saved.",
        )

    item = SavedNews(
        user_id=current_user.id,
        external_id=body.external_id,
        headline=body.headline,
        source=body.source,
        url=body.url,
        image=body.image,
        summary=body.summary,
        category=body.category,
        related=body.related,
        published_at=body.datetime,
    )
    db.add(item)
    db.commit()
    db.refresh(item)

    return SavedNewsResponse(
        id=item.id,
        external_id=item.external_id,
        category=item.category,
        datetime=item.published_at,
        headline=item.headline,
        image=item.image,
        related=item.related,
        source=item.source,
        summary=item.summary,
        url=item.url,
    )


@router.delete("/news/saved/{saved_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_saved_news_item(
    saved_id: int,
    current_user: Profile = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete one saved news record owned by the current user."""
    item = (
        db.query(SavedNews)
        .filter(SavedNews.id == saved_id, SavedNews.user_id == current_user.id)
        .first()
    )
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Saved news not found")

    db.delete(item)
    db.commit()


@router.get("/quote/{symbol}", response_model=StockQuote)
def get_stock_quote(symbol: str):
    """Return a real-time quote for the given ticker symbol using yfinance."""
    symbol = symbol.upper().strip()
    ticker = yf.Ticker(symbol)

    try:
        info = ticker.info
    except Exception:
        raise HTTPException(status_code=404, detail=f"Symbol '{symbol}' not found")

    if not info or info.get("regularMarketPrice") is None:
        raise HTTPException(status_code=404, detail=f"Symbol '{symbol}' not found")

    price = info.get("regularMarketPrice") or info.get("currentPrice") or 0.0
    prev_close = info.get("regularMarketPreviousClose") or info.get("previousClose") or price
    change = round(price - prev_close, 2)
    change_pct = round((change / prev_close) * 100, 2) if prev_close else 0.0

    return StockQuote(
        symbol=symbol,
        name=info.get("shortName") or info.get("longName") or symbol,
        price=round(price, 2),
        change=_safe(change),
        changePercent=_safe(change_pct),
        volume=info.get("regularMarketVolume") or info.get("volume") or 0,
    )


@router.get("/search", response_model=List[StockSearchResult])
def search_stocks(q: str = Query(..., min_length=1, description="Search query")):
    """Search for stocks/tickers matching the query string using yfinance."""
    try:
        search = yf.Search(q, max_results=10)
        quotes = search.quotes  # list of dicts
    except Exception:
        # Fallback: return empty list if yfinance search fails
        return []

    results: List[StockSearchResult] = []
    for item in quotes:
        # Only include equities, skip ETFs, mutual funds, crypto, etc.
        quote_type = item.get("quoteType", "").upper()
        if quote_type != "EQUITY":
            continue

        sym = item.get("symbol", "")
        name = (
            item.get("shortname")
            or item.get("shortName")
            or item.get("longname")
            or item.get("longName")
            or ""
        )
        if sym:
            results.append(StockSearchResult(symbol=sym, name=name))

    return results


# ── helpers ──────────────────────────────────────────────────────────────────
def _safe(value: float) -> float:
    """Return 0.0 for NaN / Inf, otherwise the value itself."""
    if math.isnan(value) or math.isinf(value):
        return 0.0
    return value
