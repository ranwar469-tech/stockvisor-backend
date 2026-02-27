"""Pydantic schemas for insights responses."""

from pydantic import BaseModel


class SentimentItem(BaseModel):
    """Single sentiment prediction item."""
    label: str
    score: float
