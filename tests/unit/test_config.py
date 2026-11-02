"""Unit tests for app.config."""

import pytest

from app.config import Settings, get_settings


def test_settings_default_values(clean_env: pytest.MonkeyPatch) -> None:
    """Verify that Settings loads with expected default values."""
    settings = Settings(_env_file=None)

    assert settings.anthropic_api_key == ""
    assert settings.llm_model == "claude-haiku-4-5"
    assert settings.llm_temperature == 0.0
    assert settings.database_admin_url == "postgresql://postgres:postgres@localhost:5432/chinook"
    assert (
        settings.database_readonly_url
        == "postgresql://sqlpilot_readonly:readonly_pass@localhost:5432/chinook"
    )
    assert settings.default_row_limit == 100
    assert settings.max_validation_retries == 3
    assert settings.explain_cost_threshold == 500.0
    assert settings.explain_rows_threshold == 1000
    assert settings.enable_llm_risk_classifier is False
    assert settings.langfuse_public_key == ""
    assert settings.langfuse_secret_key == ""
    assert settings.langfuse_host == "https://cloud.langfuse.com"
    assert settings.log_level == "INFO"
    assert settings.log_json is False


def test_settings_environment_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify that environment variables properly override default values."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-anthropic-key")
    monkeypatch.setenv("LLM_MODEL", "claude-3-opus-20240229")
    monkeypatch.setenv("LLM_TEMPERATURE", "0.7")
    monkeypatch.setenv("DATABASE_ADMIN_URL", "postgresql://admin:secret@pg:5432/testdb")
    monkeypatch.setenv("DATABASE_READONLY_URL", "postgresql://ro:secret@pg:5432/testdb")
    monkeypatch.setenv("DEFAULT_ROW_LIMIT", "250")
    monkeypatch.setenv("MAX_VALIDATION_RETRIES", "5")
    monkeypatch.setenv("EXPLAIN_COST_THRESHOLD", "1200.5")
    monkeypatch.setenv("EXPLAIN_ROWS_THRESHOLD", "5000")
    monkeypatch.setenv("ENABLE_LLM_RISK_CLASSIFIER", "true")
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-lf-test")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk-lf-test")
    monkeypatch.setenv("LANGFUSE_HOST", "https://custom.langfuse.com")
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("LOG_JSON", "true")

    settings = Settings(_env_file=None)

    assert settings.anthropic_api_key == "test-anthropic-key"
    assert settings.llm_model == "claude-3-opus-20240229"
    assert settings.llm_temperature == 0.7
    assert settings.database_admin_url == "postgresql://admin:secret@pg:5432/testdb"
    assert settings.database_readonly_url == "postgresql://ro:secret@pg:5432/testdb"
    assert settings.default_row_limit == 250
    assert settings.max_validation_retries == 5
    assert settings.explain_cost_threshold == 1200.5
    assert settings.explain_rows_threshold == 5000
    assert settings.enable_llm_risk_classifier is True
    assert settings.langfuse_public_key == "pk-lf-test"
    assert settings.langfuse_secret_key == "sk-lf-test"
    assert settings.langfuse_host == "https://custom.langfuse.com"
    assert settings.log_level == "DEBUG"
    assert settings.log_json is True


def test_settings_direct_kwargs() -> None:
    """Verify that settings can be passed directly as arguments."""
    settings = Settings(
        _env_file=None,
        llm_model="custom-model",
        default_row_limit=42,
        enable_llm_risk_classifier=True,
        log_level="WARNING",
        log_json=True,
    )
    assert settings.llm_model == "custom-model"
    assert settings.default_row_limit == 42
    assert settings.enable_llm_risk_classifier is True
    assert settings.log_level == "WARNING"
    assert settings.log_json is True


def test_get_settings_cached() -> None:
    """Verify that get_settings() returns a cached Settings singleton."""
    s1 = get_settings()
    s2 = get_settings()
    assert s1 is s2
