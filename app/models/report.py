"""Report model for user-submitted moderation reports."""

from sqlalchemy import Column, DateTime, Integer, String, Text, func

from app.database import Base


class Report(Base):
    __tablename__ = "reports"

    id = Column(Integer, primary_key=True, autoincrement=True)
    target_type = Column(String(20), nullable=False)  # "thread" or "post"
    target_id = Column(Integer, nullable=False)
    reason = Column(String(120), nullable=False)
    details = Column(Text, nullable=True)
    reported_by = Column(String, nullable=False)
    created_at = Column(DateTime, server_default=func.now())
