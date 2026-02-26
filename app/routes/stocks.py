"""Stock data routes — quotes and search powered by yfinance."""

import math
from typing import List

from fastapi import APIRouter, HTTPException, Query
import yfinance as yf

from app.schemas.stocks import StockQuote, StockSearchResult

router = APIRouter(prefix="/stocks", tags=["stocks"])


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
