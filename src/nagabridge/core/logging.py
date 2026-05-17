"""Logging configuration helpers (ADR-012)."""

from __future__ import annotations

import logging
import logging.handlers
from pathlib import Path

LOG_DIR = Path("/var/log/nagabridge")
LOG_FORMAT = "%(asctime)s [%(levelname)-5s] [%(name)-12s] %(message)s"
LOG_DATE_FMT = "%Y-%m-%d %H:%M:%S"
ROTATE_SUFFIX = "%Y-%m-%d"
BACKUP_COUNT = 7  # one week


def _rotating_file_handler(path: Path, level: int) -> logging.handlers.TimedRotatingFileHandler:
    """Create a daily-rotating file handler for *path*."""
    path.parent.mkdir(parents=True, exist_ok=True)
    handler = logging.handlers.TimedRotatingFileHandler(
        filename=str(path),
        when="midnight",
        backupCount=BACKUP_COUNT,
        encoding="utf-8",
    )
    handler.suffix = ROTATE_SUFFIX
    handler.setLevel(level)
    handler.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=LOG_DATE_FMT))
    return handler


def configure_logging(
    level: str = "INFO",
    *,
    log_dir: Path = LOG_DIR,
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

    # --- stdout handler (journalctl picks this up via systemd) ---
    stdout_handler = logging.StreamHandler()
    stdout_handler.setLevel(numeric_level)
    stdout_handler.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=LOG_DATE_FMT))

    # --- core file handler ---
    core_file_handler = _rotating_file_handler(log_dir / "nagabridge.log", numeric_level)

    root = logging.getLogger("nagabridge")
    root.setLevel(numeric_level)
    root.handlers.clear()
    root.addHandler(stdout_handler)
    root.addHandler(core_file_handler)
    root.propagate = False

    # --- per-adapter file handlers ---
    for logger_prefix, file_stem in (adapter_log_names or {}).items():
        adapter_logger = logging.getLogger(logger_prefix)
        adapter_logger.setLevel(numeric_level)
        # remove inherited handlers so messages don't double-write to core file
        adapter_logger.handlers.clear()
        adapter_logger.propagate = False
        # adapter file
        adapter_logger.addHandler(_rotating_file_handler(log_dir / f"{file_stem}.log", numeric_level))
        # still mirror to stdout via root handler
        adapter_logger.addHandler(stdout_handler)
