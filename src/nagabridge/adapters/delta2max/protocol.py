"""Delta 2 Max specific protocol helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import SupportsIndex, SupportsInt, cast

COMMAND_GET_STATUS = "get_status"
COMMAND_REFRESH = "refresh"
COMMAND_SET_AC_OUTPUT = "set_ac_output"
COMMAND_SET_DC_OUTPUT = "set_dc_output"
COMMAND_SET_XT60_INPUT_LIMIT = "set_xt60_input_limit"

_IntPayloadValue = str | bytes | bytearray | SupportsInt | SupportsIndex


@dataclass(frozen=True, slots=True)
class Delta2MaxCommand:
    """A normalized model-specific command."""

    op: str
    params: dict[str, int | bool]


def _payload_int(payload: dict[str, object], key: str, default: int) -> int:
    """Return an integer value from an untyped external payload."""
    return int(cast(_IntPayloadValue, payload.get(key, default)))


def map_command(payload: dict[str, object]) -> Delta2MaxCommand | None:
    """Map external command payloads to Delta 2 Max specific operations."""
    command = str(payload.get("command") or payload.get("type") or "").strip().lower()
    if command in {COMMAND_GET_STATUS, COMMAND_REFRESH}:
        return Delta2MaxCommand(op="status.refresh", params={})
    if command == COMMAND_SET_AC_OUTPUT:
        return Delta2MaxCommand(op="ac.output", params={"enabled": bool(payload.get("enabled", True))})
    if command == COMMAND_SET_DC_OUTPUT:
        return Delta2MaxCommand(op="dc.output", params={"enabled": bool(payload.get("enabled", True))})
    if command == COMMAND_SET_XT60_INPUT_LIMIT:
        port = _payload_int(payload, "port", 1)
        watts = _payload_int(payload, "watts", 0)
        if port not in {1, 2}:
            msg = "Delta 2 Max XT60 port must be 1 or 2"
            raise ValueError(msg)
        if watts < 0:
            msg = "Delta 2 Max XT60 input limit cannot be negative"
            raise ValueError(msg)
        return Delta2MaxCommand(op=f"xt60.{port}.limit", params={"watts": watts})
    return None
