"""Parsing helpers for Delta 2 Max payloads."""

from typing import Any


def parse_payload(raw: bytes) -> dict[str, Any]:
    """Parse a raw Delta 2 Max payload into a normalized dictionary."""
    if len(raw) >= 3:
        return {
            "message_type": "delta2max_status",
            "ac_output_watts": int(raw[0]),
            "battery_soc": int(raw[1]),
            "dual_xt60_input_watts": int(raw[2]),
        }
    return {"raw_len": len(raw)}
