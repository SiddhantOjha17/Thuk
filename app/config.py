"""Application configuration using Pydantic Settings."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Database
    database_url: str = "postgresql+asyncpg://user:password@localhost:5432/thuk"

    # Twilio WhatsApp
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_whatsapp_number: str = "whatsapp:+14155238886"

    # Encryption key for user API keys
    encryption_key: str = ""

    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = False

    # Webhook
    webhook_base_url: str = ""

    @property
    def sync_database_url(self) -> str:
        """Get synchronous database URL for Alembic migrations."""
        return self.database_url.replace("postgresql+asyncpg", "postgresql+psycopg2")


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
