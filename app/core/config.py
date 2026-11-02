"""Typed application settings, read from environment variables / .env."""

from functools import lru_cache

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def normalize_database_url(url: str) -> str:
    """postgres:// and postgresql:// both become postgresql+psycopg://."""
    url = url.strip()
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url[len(prefix) :]
    return url


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    DATABASE_URL: str
    JWT_SECRET: str = Field(min_length=16)

    ACCESS_TOKEN_MINUTES: int = Field(default=15, ge=1)
    REFRESH_TOKEN_DAYS: int = Field(default=30, ge=1)
    CORS_ORIGINS: str = "*"
    USE_PG_TRGM: bool = True
    ENVIRONMENT: str = "development"

    # Extras with safe defaults (documented in the README).
    BCRYPT_ROUNDS: int = Field(default=12, ge=4, le=16)
    RATE_LIMIT_ENABLED: bool = True
    AUTH_RATE_LIMIT: str = "20/minute"
    MAX_FAILED_LOGINS: int = 5
    LOCKOUT_MINUTES: int = 15
    DEFAULT_TIMEZONE: str = "Asia/Kolkata"
    LOG_LEVEL: str = "INFO"

    @field_validator("DATABASE_URL")
    @classmethod
    def _normalize_url(cls, v: str) -> str:
        return normalize_database_url(v)

    @model_validator(mode="after")
    def _production_checks(self) -> "Settings":
        if self.ENVIRONMENT.lower() == "production":
            if self.CORS_ORIGINS.strip() == "*":
                raise ValueError("CORS_ORIGINS must list explicit origins in production")
            if len(self.JWT_SECRET) < 32:
                raise ValueError("JWT_SECRET must be at least 32 characters in production")
        return self

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]