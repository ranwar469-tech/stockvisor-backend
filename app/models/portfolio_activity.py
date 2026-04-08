"""Portfolio activity model — immutable buy/sell transaction history."""

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, func

from app.database import Base


class PortfolioActivity(Base):
    __tablename__ = "portfolio_activities"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String, ForeignKey("profiles.id"), nullable=False)
    symbol = Column(String(10), nullable=False)
    name = Column(String(100), nullable=True)
    activity_type = Column(String(10), nullable=False)  # "buy" or "sell"
    shares = Column(Float, nullable=False)
    price = Column(Float, nullable=False)
    seeded_from_holding_id = Column(Integer, nullable=True, unique=True)
    created_at = Column(DateTime, server_default=func.now())
