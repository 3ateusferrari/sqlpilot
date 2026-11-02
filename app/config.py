"""Configuration settings for SQLPilot using Pydantic Settings."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration loaded from environment variables and .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # LLM (Claude Haiku 4.5)
    anthropic_api_key: str = ""
    llm_model: str = "claude-haiku-4-5"
    llm_temperature: float = 0.0

    # PostgreSQL
    database_admin_url: str = "postgresql://postgres:postgres@localhost:5432/chinook"
    database_readonly_url: str = (
        "postgresql://sqlpilot_readonly:readonly_pass@localhost:5432/chinook"
    )
    default_row_limit: int = 100
    max_validation_retries: int = 3

    # Classificação de Risco
    explain_cost_threshold: float = 500.0
    explain_rows_threshold: int = 1000
    enable_llm_risk_classifier: bool = False

    # Observabilidade (Langfuse)
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_host: str = "https://cloud.langfuse.com"


@lru_cache
def get_settings() -> Settings:
    """Return a cached instance of application settings."""
    return Settings()


settings = get_settings()
