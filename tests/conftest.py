"""Pytest fixtures and configuration."""

import pytest


@pytest.fixture
def clean_env(monkeypatch: pytest.MonkeyPatch) -> pytest.MonkeyPatch:
    """Fixture that clears relevant SQLPilot environment variables."""
    keys_to_clear = [
        "ANTHROPIC_API_KEY",
        "LLM_MODEL",
        "LLM_TEMPERATURE",
        "DATABASE_ADMIN_URL",
        "DATABASE_READONLY_URL",
        "DEFAULT_ROW_LIMIT",
        "MAX_VALIDATION_RETRIES",
        "EXPLAIN_COST_THRESHOLD",
        "EXPLAIN_ROWS_THRESHOLD",
        "ENABLE_LLM_RISK_CLASSIFIER",
        "LANGFUSE_PUBLIC_KEY",
        "LANGFUSE_SECRET_KEY",
        "LANGFUSE_HOST",
        "LOG_LEVEL",
        "LOG_JSON",
    ]
    for key in keys_to_clear:
        monkeypatch.delenv(key, raising=False)
    return monkeypatch
