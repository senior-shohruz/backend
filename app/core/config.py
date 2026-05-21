"""Application configuration using Pydantic Settings."""
from functools import lru_cache
from typing import List
from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # App
    APP_NAME: str = "Frontend Learning Platform"
    DEBUG: bool = False
    API_V1_PREFIX: str = "/api/v1"

    # Database — SYNC_DATABASE_URL is auto-derived if not set
    DATABASE_URL: str = "sqlite+aiosqlite:///./app.db"
    SYNC_DATABASE_URL: str = ""

    # JWT
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # CORS
    ALLOWED_ORIGINS: str = "http://localhost:3000"

    # AI
    ANTHROPIC_API_KEY: str = ""

    # First admin
    FIRST_ADMIN_EMAIL: str = "admin@platform.com"
    FIRST_ADMIN_PASSWORD: str = "Admin123!"
    FIRST_ADMIN_USERNAME: str = "admin"

    @model_validator(mode="after")
    def configure_database_urls(self) -> "Settings":
        url = self.DATABASE_URL

        if not url.startswith("sqlite"):
            # Render gives postgres:// — convert to postgresql://
            if url.startswith("postgres://"):
                url = "postgresql" + url[8:]

            # Ensure async URL uses +asyncpg driver
            if url.startswith("postgresql://"):
                self.DATABASE_URL = url.replace("postgresql://", "postgresql+asyncpg://", 1)
            elif url.startswith("postgresql+asyncpg://"):
                self.DATABASE_URL = url

        # Auto-derive sync URL if not explicitly set
        if not self.SYNC_DATABASE_URL:
            if self.DATABASE_URL.startswith("sqlite+aiosqlite://"):
                self.SYNC_DATABASE_URL = self.DATABASE_URL.replace(
                    "sqlite+aiosqlite://", "sqlite://", 1
                )
            else:
                self.SYNC_DATABASE_URL = self.DATABASE_URL.replace(
                    "postgresql+asyncpg://", "postgresql://", 1
                )

        return self

    @property
    def cors_origins(self) -> List[str]:
        return [o.strip() for o in self.ALLOWED_ORIGINS.split(",") if o.strip()]


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
