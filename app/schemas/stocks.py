"""Pydantic schemas for stock data."""

from pydantic import BaseModel


class StockQuote(BaseModel):
    """Shape returned by GET /stocks/quote/{symbol}."""
    symbol: str
    name: str
    price: float
    change: float
    changePercent: float
    volume: int


class StockSearchResult(BaseModel):
    """Shape returned by GET /stocks/search."""
    symbol: str
    name: str
