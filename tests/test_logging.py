"""Tests for logging configuration helpers (ADR-012)."""

from __future__ import annotations

import logging
import logging.handlers
from pathlib import Path

from nagabridge.core.logging import configure_logging


def test_rotating_handler_namer_produces_adr012_filename(tmp_path: Path) -> None:
    """Rotated filenames must follow <stem>.<date><suffix> per ADR-012."""
    configure_logging("INFO", log_dir=tmp_path)

    root = logging.getLogger("nagabridge")
    file_handlers = [h for h in root.handlers if isinstance(h, logging.handlers.TimedRotatingFileHandler)]
    assert file_handlers, "Expected at least one TimedRotatingFileHandler"

    handler = file_handlers[0]
    default_name = str(tmp_path / "nagabridge.log.2026-05-03")
    result = handler.namer(default_name)

    assert result == str(tmp_path / "nagabridge.2026-05-03.log")


def test_rotating_handler_namer_works_for_adapter_log(tmp_path: Path) -> None:
    """Adapter log filenames must also follow ADR-012 naming."""
    configure_logging(
        "INFO",
        log_dir=tmp_path,
        adapter_log_names={"nagabridge.adapters.mqtt": "mqtt"},
    )

    adapter_logger = logging.getLogger("nagabridge.adapters.mqtt")
    file_handlers = [h for h in adapter_logger.handlers if isinstance(h, logging.handlers.TimedRotatingFileHandler)]
    assert file_handlers, "Expected TimedRotatingFileHandler on adapter logger"

    handler = file_handlers[0]
    default_name = str(tmp_path / "mqtt.log.2026-05-03")
    result = handler.namer(default_name)

    assert result == str(tmp_path / "mqtt.2026-05-03.log")
