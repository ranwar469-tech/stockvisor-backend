"""Application settings loaded from .env via pydantic-settings."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str
    SUPABASE_URL: str
    SUPABASE_ANON_KEY: str
    SUPABASE_SERVICE_ROLE_KEY: str
    SUPABASE_JWT_SECRET: str
    FINNHUB_API_KEY: str
    HF_TOKEN:str

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
