"""PowerStream adapter package."""

from __future__ import annotations

from importlib import import_module
from typing import Any

from .adapter import PowerstreamAdapter, PowerstreamAdapterConfig

_PROTOCOL_EXPORTS = {
    "COMMAND_ID_AUTH",
    "COMMAND_ID_GET_STATUS",
    "COMMAND_ID_HEARTBEAT",
    "COMMAND_ID_SET_LOAD_POWER",
    "COMMAND_SET_COMMON",
    "COMMAND_SET_POWERSTREAM",
    "Packet",
    "Type1Crypto",
    "UUID_NOTIFY",
    "UUID_WRITE",
    "build_auth_md5",
    "crc8",
    "crc16",
    "encode_simple",
    "parse_simple",
}

__all__ = ["PowerstreamAdapter", "PowerstreamAdapterConfig", *_PROTOCOL_EXPORTS]


def __getattr__(name: str) -> Any:
    """Lazily expose protocol helpers without importing crypto for adapter-only use."""
    if name in _PROTOCOL_EXPORTS:
        return getattr(import_module(".protocol", __name__), name)
    raise AttributeError(name)
