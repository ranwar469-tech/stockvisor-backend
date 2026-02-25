"""Pydantic schemas for stock data."""

from pydantic import BaseModel, Field


class StockQuote(BaseModel):
    """Shape returned by GET /stocks/quote/{symbol}."""
    symbol: str
    name: str
    price: float
    change: float
    changePercent: float = Field(alias="changePercent")
    volume: int

    model_config = {"populate_by_name": True}


class StockSearchResult(BaseModel):
    """Shape returned by GET /stocks/search."""
    symbol: str
    name: str
