"""Bio-Chain v2 — Centralized configuration via Pydantic BaseSettings.

Membaca dari .env file atau environment variables.
"""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = "postgresql+asyncpg://biochain:biochain_dev_2026@localhost:5432/biochain"
    DATABASE_URL_SYNC: str = "postgresql://biochain:biochain_dev_2026@localhost:5432/biochain"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # Auth
    JWT_SECRET: str = "biochain-dev-secret-change-in-production-2026"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 480  # 8 jam

    # Rate Limiting
    RATE_LIMIT_REQUESTS: int = 100
    RATE_LIMIT_WINDOW_SECONDS: int = 60

    # App
    APP_NAME: str = "Bio-Chain API"
    DEBUG: bool = True

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
