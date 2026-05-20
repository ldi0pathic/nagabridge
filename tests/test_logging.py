"""Tests for logging configuration helpers (ADR-012)."""

from __future__ import annotations

import logging
import logging.handlers
from pathlib import Path

from nagabridge.core.logging import _ShortNameFormatter, configure_logging


def test_file_handler_type_is_watched(tmp_path: Path) -> None:
    """File handler must be WatchedFileHandler so logrotate can rotate without restart."""
    configure_logging("INFO", log_dir=tmp_path)

    root = logging.getLogger("nagabridge")
    file_handlers = [h for h in root.handlers if isinstance(h, logging.handlers.WatchedFileHandler)]
    assert file_handlers, "Expected at least one WatchedFileHandler on root logger"


def test_adapter_file_handler_type_is_watched(tmp_path: Path) -> None:
    """Adapter logger must also use WatchedFileHandler."""
    configure_logging(
        "INFO",
        log_dir=tmp_path,
        adapter_log_names={"nagabridge.adapters.mqtt": "mqtt"},
    )

    adapter_logger = logging.getLogger("nagabridge.adapters.mqtt")
    file_handlers = [h for h in adapter_logger.handlers if isinstance(h, logging.handlers.WatchedFileHandler)]
    assert file_handlers, "Expected WatchedFileHandler on adapter logger"


def test_short_name_formatter_strips_prefix() -> None:
    """Formatter must show only the last logger-name segment."""
    formatter = _ShortNameFormatter("%(name)s")
    record = logging.LogRecord(
        name="nagabridge.adapters.powerstream.powerstream",
        level=logging.INFO,
        pathname="",
        lineno=0,
        msg="test",
        args=(),
        exc_info=None,
    )
    assert formatter.format(record) == "powerstream"


def test_short_name_formatter_leaves_short_name_unchanged() -> None:
    """Single-segment names must pass through unchanged."""
    formatter = _ShortNameFormatter("%(name)s")
    record = logging.LogRecord(
        name="bus",
        level=logging.INFO,
        pathname="",
        lineno=0,
        msg="test",
        args=(),
        exc_info=None,
    )
    assert formatter.format(record) == "bus"


def test_short_name_formatter_does_not_mutate_original_record() -> None:
    """Formatter must not alter the original LogRecord name."""
    formatter = _ShortNameFormatter("%(name)s")
    record = logging.LogRecord(
        name="nagabridge.adapters.mqtt.mqtt",
        level=logging.INFO,
        pathname="",
        lineno=0,
        msg="test",
        args=(),
        exc_info=None,
    )
    formatter.format(record)
    assert record.name == "nagabridge.adapters.mqtt.mqtt"
