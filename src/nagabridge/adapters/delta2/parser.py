"""Parsing helpers for Delta 2 payloads."""

from typing import Any


def parse_payload(raw: bytes) -> dict[str, Any]:
    """Parse a raw Delta 2 payload into a normalized dictionary."""
    if len(raw) >= 2:
        return {
            "message_type": "delta2_status",
            "ac_output_watts": int(raw[0]),
            "battery_soc": int(raw[1]),
        }
    return {"raw_len": len(raw)}
