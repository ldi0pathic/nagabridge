"""Protocol structures for Delta 2 Max communication."""

from __future__ import annotations

from dataclasses import dataclass


class Type7Crypto:
    """Represent Delta 2 Max type-7 crypto metadata."""


@dataclass(slots=True)
class Packet:
    """Represent a decoded Delta 2 Max packet layout."""

    payload: bytes


def encode_command(command: str, payload: dict[str, object]) -> bytes:
    """Encode a supported command into a BLE packet."""
    if command == "set_ac_output":
        watts = int(payload["watts"])
        return bytes([0xB1, watts & 0xFF])
    if command in {"get_status", "refresh"}:
        return bytes([0x01])
    raise ValueError(f"Unsupported command: {command}")
