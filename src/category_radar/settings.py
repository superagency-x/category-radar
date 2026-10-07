"""Application settings from environment variables."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="RADAR_",
        extra="ignore",
    )

    user_agent: str | None = None
    slack_webhook_url: str | None = None
    alert_webhook_url: str | None = None
    ecb_api_key: str | None = None
    supabase_url: str | None = None
    database_url: str | None = None


settings = Settings()
