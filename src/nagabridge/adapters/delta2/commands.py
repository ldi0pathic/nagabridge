"""Delta 2 command encoders."""

from __future__ import annotations

from typing import Any

from .protocol import CMD_REFRESH, CMD_SET_AC_OUTPUT, CMD_SET_XT60_INPUT, KIND_COMMAND_ACK, encode_packet


def encode_command(payload: dict[str, Any]) -> bytes | None:
    """Map generic command payloads to Delta 2 BLE packets."""
    command = payload.get("command") or payload.get("type")
    if command in {"get_status", "refresh"}:
        return encode_packet(KIND_COMMAND_ACK, bytes((CMD_REFRESH,)))
    if command == "set_ac_output":
        enabled = bool(payload.get("enabled", True))
        return encode_packet(KIND_COMMAND_ACK, bytes((CMD_SET_AC_OUTPUT, 1 if enabled else 0)))
    if command == "set_xt60_input":
        watts = int(payload.get("watts", 0))
        watts = max(0, min(500, watts))
        return encode_packet(KIND_COMMAND_ACK, bytes((CMD_SET_XT60_INPUT,)) + watts.to_bytes(2, "big"))
    return None
