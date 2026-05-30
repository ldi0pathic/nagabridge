"""Delta 2 payload parser."""

from __future__ import annotations

from typing import Any

# Telemetry payload layout:
# [0..1] battery_percent uint16 (x10)
# [2..3] output_watts uint16
# [4..5] input_watts uint16
# [6..7] xt60_input_watts uint16
# [8]    ac_output_enabled bool

def parse_status_payload(raw: bytes) -> dict[str, Any]:
    """Parse Delta 2 status payload fields relevant for this adapter."""
    if len(raw) < 9:
        return {"raw_len": len(raw)}

    battery_tenths = int.from_bytes(raw[0:2], "big")
    return {
        "battery_percent": round(battery_tenths / 10.0, 1),
        "output_watts": int.from_bytes(raw[2:4], "big"),
        "input_watts": int.from_bytes(raw[4:6], "big"),
        "xt60_input_watts": int.from_bytes(raw[6:8], "big"),
        "ac_output_enabled": bool(raw[8]),
    }
