"""Profile model — mirrors Supabase auth.users into public schema."""

from sqlalchemy import Column, DateTime, String, func

from app.database import Base


class Profile(Base):
    __tablename__ = "profiles"

    id = Column(String, primary_key=True)  # UUID from Supabase auth.users
    username = Column(String, unique=True, nullable=False)
    email = Column(String, unique=True, nullable=False)
    role = Column(String(20), nullable=False, default="user", server_default="user")
    created_at = Column(DateTime, server_default=func.now())
