"""SavedNews model — tracks news articles a user saved."""

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func

from app.database import Base


class SavedNews(Base):
    __tablename__ = "saved_news"
    __table_args__ = (
        UniqueConstraint("user_id", "external_id", name="uq_saved_news_user_external"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String, ForeignKey("profiles.id"), nullable=False)
    external_id = Column(Integer, nullable=False)
    headline = Column(String(300), nullable=False)
    source = Column(String(120), nullable=False)
    url = Column(String(1000), nullable=False)
    image = Column(String(1000), nullable=True)
    summary = Column(Text, nullable=True)
    category = Column(String(120), nullable=True)
    related = Column(String(255), nullable=True)
    published_at = Column(Integer, nullable=False)
    saved_at = Column(DateTime, server_default=func.now())
