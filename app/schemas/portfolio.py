"""Pydantic schemas for portfolio holdings."""

from pydantic import BaseModel, Field


class HoldingCreate(BaseModel):
    """Request body for POST /portfolio/."""
    symbol: str
    quantity: float
    purchase_price: float


class HoldingSell(BaseModel):
    """Request body for POST /portfolio/sell."""
    symbol: str
    quantity: float


class HoldingResponse(BaseModel):
    """Response body for a portfolio holding (camelCase aliases for frontend)."""
    id: int
    symbol: str
    name: str | None = None
    quantity: float
    purchase_price: float = Field(alias="purchasePrice")
    current_price: float = Field(alias="currentPrice")
    daily_change: float = Field(alias="dailyChange")
    daily_change_percent: float = Field(alias="dailyChangePercent")

    class Config:
        from_attributes = True
        populate_by_name = True
