"""
Application Settings

Centralized configuration management using Pydantic Settings.
"""

from typing import List
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
    )

    # Application
    APP_NAME: str = "cerberus"
    APP_ENV: str = "development"
    DEBUG: bool = True
    LOG_LEVEL: str = "INFO"

    # Database
    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/cerberus"
    )
    DATABASE_POOL_SIZE: int = 20
    DATABASE_MAX_OVERFLOW: int = 10

    # Migrations
    # When True, runs alembic migrations on app startup
    # Uses PostgreSQL advisory lock to prevent race conditions with multiple instances
    RUN_MIGRATIONS_ON_STARTUP: bool = True

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_POOL_SIZE: int = 10

    # Security
    SECRET_KEY: str = Field(default="change-me-in-production")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    API_KEY_PREFIX: str = "sk-"

    # CORS
    CORS_ORIGINS: List[str] = ["http://localhost:3000"]

    # MCP Proxy Settings
    MCP_REQUEST_TIMEOUT_SECONDS: float = 30.0
    MCP_MAX_RETRIES: int = 2
    MCP_MAX_KEEPALIVE_CONNECTIONS: int = 20
    MCP_MAX_CONNECTIONS: int = 100

    # Proxy Header Forwarding Settings
    # Whether to forward client's Authorization header to upstream MCP server
    PROXY_FORWARD_AUTHORIZATION: bool = False
    # Header name for gateway request ID
    PROXY_REQUEST_ID_HEADER: str = "X-Gateway-Request-ID"
    # Header name for forwarded client IP
    PROXY_FORWARDED_FOR_HEADER: str = "X-Forwarded-For"
    # Whether to forward all client headers (except blocked ones)
    PROXY_FORWARD_ALL_HEADERS: bool = False
    # Comma-separated list of additional headers to block from forwarding
    PROXY_BLOCKED_HEADERS: str = ""
    # Comma-separated list of headers to forward (when PROXY_FORWARD_ALL_HEADERS=False)
    PROXY_FORWARD_HEADERS: str = "accept,accept-language,content-type"

    @property
    def proxy_blocked_headers_list(self) -> set[str]:
        """Parse blocked headers into a set."""
        if not self.PROXY_BLOCKED_HEADERS:
            return set()
        return {h.strip().lower() for h in self.PROXY_BLOCKED_HEADERS.split(",") if h.strip()}

    @property
    def proxy_forward_headers_list(self) -> set[str]:
        """Parse forward headers into a set."""
        if not self.PROXY_FORWARD_HEADERS:
            return set()
        return {h.strip().lower() for h in self.PROXY_FORWARD_HEADERS.split(",") if h.strip()}

    @property
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.APP_ENV == "production"

    @property
    def is_development(self) -> bool:
        """Check if running in development or local environment."""
        return self.APP_ENV in ("development", "local")


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


settings = get_settings()
