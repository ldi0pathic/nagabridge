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
}


def sanitize_state(payload: dict[str, Any]) -> dict[str, Any]:
    """Keep only model-valid, stable Delta 2 Max state fields."""
    return {key: payload[key] for key in ALLOWED_STATE_FIELDS if key in payload}
