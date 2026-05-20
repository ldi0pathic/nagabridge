"""Logging configuration helpers (ADR-012)."""

from __future__ import annotations

import copy
import logging
import logging.handlers
from pathlib import Path

LOG_DIR = Path("/var/log/nagabridge")
LOG_FORMAT = "%(asctime)s [%(levelname)-5s] [%(name)-12s] %(message)s"
LOG_DATE_FMT = "%Y-%m-%d %H:%M:%S"


class _ShortNameFormatter(logging.Formatter):
    """Formatter that shows only the last dotted segment of the logger name.

    Turns "nagabridge.adapters.powerstream.powerstream" into "powerstream"
    so the name column in the log output stays within 12 chars.
    """

    def format(self, record: logging.LogRecord) -> str:
        record = copy.copy(record)
        record.name = record.name.rsplit(".", 1)[-1]
        return super().format(record)


def _file_handler(path: Path, level: int) -> logging.handlers.WatchedFileHandler:
    """Create a WatchedFileHandler for *path*.

    Rotation is managed externally by logrotate (ADR-012).
    WatchedFileHandler detects when logrotate moves the file and reopens it.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    handler = logging.handlers.WatchedFileHandler(str(path), encoding="utf-8")
    handler.setLevel(level)
    handler.setFormatter(_ShortNameFormatter(LOG_FORMAT, datefmt=LOG_DATE_FMT))
    return handler


def configure_logging(
    level: str = "INFO",
    *,
    log_dir: Path | None = None,
    adapter_log_names: dict[str, str] | None = None,
) -> None:
    """Configure process-wide logging with stdout + per-adapter file output.

    Args:
        level: Minimum log level (DEBUG|INFO|WARNING|ERROR).
        log_dir: Directory for log files (default: /var/log/nagabridge/).
        adapter_log_names: Mapping of logger-name-prefix → log-file-stem.
            Example: {"nagabridge.adapters.powerstream": "ble-ecoflow",
                      "nagabridge.adapters.mqtt": "mqtt"}
            Core loggers (nagabridge.core, nagabridge.main) always go to
            nagabridge.log.
    """
    numeric_level = getattr(logging, level.upper(), logging.INFO)

    formatter = _ShortNameFormatter(LOG_FORMAT, datefmt=LOG_DATE_FMT)

    # --- stdout handler (journalctl picks this up via systemd) ---
    stdout_handler = logging.StreamHandler()
    stdout_handler.setLevel(numeric_level)
    stdout_handler.setFormatter(formatter)

    root = logging.getLogger("nagabridge")
    root.setLevel(numeric_level)
    root.handlers.clear()
    root.addHandler(stdout_handler)

    # --- core file handler ---
    if log_dir is not None:
        root.addHandler(_file_handler(log_dir / "nagabridge.log", numeric_level))

    root.propagate = False

    # --- per-adapter file handlers ---
    for logger_prefix, file_stem in (adapter_log_names or {}).items():
        adapter_logger = logging.getLogger(logger_prefix)
        adapter_logger.setLevel(numeric_level)
        # remove inherited handlers so messages don't double-write to core file
        adapter_logger.handlers.clear()
        adapter_logger.propagate = False
        # adapter file
        if log_dir is not None:
            adapter_logger.addHandler(_file_handler(log_dir / f"{file_stem}.log", numeric_level))
        # still mirror to stdout via root handler
        adapter_logger.addHandler(stdout_handler)
