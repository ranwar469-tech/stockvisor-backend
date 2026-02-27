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


class MarketStatus(BaseModel):
    """Shape returned by GET /stocks/marketStatus."""
    status: str


class NewsItem(BaseModel):
    """Shape returned by GET /stocks/news."""
    category: str
    datetime: int
    headline: str
    id: int
    image: str
    related: str
    source: str
    summary: str
    url: str


class StockRecommendation(BaseModel):
    """Shape returned by GET /stocks/recommendations."""
    buy: int
    hold: int
    period: str
    sell: int
    strongBuy: int
    strongSell: int
    symbol: str


class SavedNewsCreate(BaseModel):
    """Request body for saving a news article to a user's account."""
    external_id: int
    category: str
    datetime: int
    headline: str
    image: str | None = None
    related: str | None = None
    source: str
    summary: str | None = None
    url: str


class SavedNewsResponse(BaseModel):
    """Saved news item returned from the database."""
    id: int
    external_id: int
    category: str | None = None
    datetime: int
    headline: str
    image: str | None = None
    related: str | None = None
    source: str
    summary: str | None = None
    url: str

    class Config:
        from_attributes = True
