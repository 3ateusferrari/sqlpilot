"""LLM factory using Claude Haiku 4.5 via ChatAnthropic."""

from langchain_anthropic import ChatAnthropic
from pydantic import SecretStr

from app.config import settings


def get_llm(
    model: str | None = None,
    temperature: float = 0.0,
) -> ChatAnthropic:
    """Return an instance of ChatAnthropic configured with application settings.

    Args:
        model: Model identifier override (defaults to settings.llm_model).
        temperature: Sampling temperature (defaults to 0.0 for deterministic execution).

    Returns:
        Configured ChatAnthropic instance.
    """
    chosen_model = model or settings.llm_model
    raw_key = settings.anthropic_api_key.strip() if settings.anthropic_api_key else "mock-key"
    api_key = SecretStr(raw_key)

    return ChatAnthropic(  # type: ignore[call-arg]
        model=chosen_model,
        temperature=temperature,
        api_key=api_key,
    )
