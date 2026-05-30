"""Parsing helpers for Delta 2 Max payloads."""

from __future__ import annotations

from typing import Any

ALLOWED_STATE_FIELDS = {
    "online",
    "ac_output_enabled",
    "dc_output_enabled",
    "battery_percent",
    "input_watts_total",
    "input_xt60_1_watts",
    "input_xt60_2_watts",
    "output_watts",
    "temperature_c",
    "last_command",
    "last_error",
    "message_type",
    "ac_output_watts",
    "battery_soc",
    "dual_xt60_input_watts",
}


def sanitize_state(payload: dict[str, Any]) -> dict[str, Any]:
    """Keep only model-valid, stable Delta 2 Max state fields."""
    return {key: payload[key] for key in ALLOWED_STATE_FIELDS if key in payload}


def parse_payload(raw: bytes) -> dict[str, Any]:
    """Parse the compact Delta 2 Max status payload used by legacy BLE tests."""
    if len(raw) < 3:
        return {"message_type": "unknown", "raw_len": len(raw), "raw_hex": raw.hex()}
    return {
        "message_type": "delta2max_status",
        "ac_output_watts": raw[0],
        "battery_soc": raw[1],
        "dual_xt60_input_watts": raw[2],
    }
