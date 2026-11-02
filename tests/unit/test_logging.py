"""Unit tests for app.logging."""

import json
import logging

import pytest

from app.logging import get_logger, setup_logging


def test_get_logger() -> None:
    """Verify that get_logger returns a structlog logger."""
    logger = get_logger("test")
    assert logger is not None


def test_setup_logging_console(capsys: pytest.CaptureFixture[str]) -> None:
    """Verify that logging works with console renderer and emits formatted output."""
    setup_logging(json_format=False)
    logger = get_logger("test_console")
    logger.info("console_test_event", key="console_value")

    captured = capsys.readouterr()
    assert "console_test_event" in captured.out
    assert "console_value" in captured.out
    assert "sqlpilot" in captured.out


def test_setup_logging_json(capsys: pytest.CaptureFixture[str]) -> None:
    """Verify that logging works with JSON renderer and outputs valid JSON."""
    setup_logging(json_format=True)
    logger = get_logger("test_json")
    logger.info("json_test_event", key="json_val")

    captured = capsys.readouterr()
    data = json.loads(captured.out.strip())

    assert data["event"] == "json_test_event"
    assert data["app"] == "sqlpilot"
    assert data["key"] == "json_val"
    assert data["level"] == "info"
    assert "timestamp" in data
    assert data["logger"] == "test_json"

    # Reset back to default
    setup_logging()


def test_stdlib_logging_bridge(capsys: pytest.CaptureFixture[str]) -> None:
    """Verify that stdlib loggers route through structlog without crashing on foreign_pre_chain."""
    setup_logging(json_format=True)
    stdlib_logger = logging.getLogger("test_stdlib")
    stdlib_logger.info("stdlib_event_message")

    captured = capsys.readouterr()
    data = json.loads(captured.out.strip())

    assert data["event"] == "stdlib_event_message"
    assert data["app"] == "sqlpilot"
    assert data["logger"] == "test_stdlib"

    # Reset back to default
    setup_logging()


def test_setup_logging_level_filtering(capsys: pytest.CaptureFixture[str]) -> None:
    """Verify that log_level properly filters messages below threshold."""
    setup_logging(json_format=False, log_level="WARNING")
    logger = get_logger("test_filter")

    logger.info("info_should_be_filtered")
    captured = capsys.readouterr()
    assert "info_should_be_filtered" not in captured.out

    logger.warning("warning_should_appear")
    captured = capsys.readouterr()
    assert "warning_should_appear" in captured.out

    # Reset back to default
    setup_logging()
