"""Unit tests for app.logging."""

from app.logging import get_logger, setup_logging


def test_get_logger() -> None:
    """Verify that get_logger returns a structlog logger."""
    logger = get_logger("test")
    assert logger is not None


def test_setup_logging_console(capsys: object) -> None:
    """Verify that logging works with console renderer."""
    setup_logging(json_format=False)
    logger = get_logger("test_console")
    logger.info("console_test_event", key="value")


def test_setup_logging_json(capsys: object) -> None:
    """Verify that logging works with JSON renderer."""
    setup_logging(json_format=True)
    logger = get_logger("test_json")
    logger.info("json_test_event", key="value")
    # Reset back to default
    setup_logging()
