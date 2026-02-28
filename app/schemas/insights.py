"""Pydantic schemas for insights responses."""

from pydantic import BaseModel


class SentimentItem(BaseModel):
    """Single sentiment prediction item."""
    label: str
    score: float


class AlertResponse(BaseModel):
    """Response payload for AI-generated alert summaries."""
    ai_alert_1: str
    ai_alert_2: str
    ai_alert_3: str
    ai_alert_4: str
    

